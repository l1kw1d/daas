import logging
from django.db import transaction


from ...models import Sample, RedisJob
from ..redis_manager import RedisManager
from .abstract_new_file import AbstractNewFile


class NewSampleFile(AbstractNewFile):
    def __init__(self, file_name: str, content: bytes, identifier: str = 'zip',
                 force_reprocess: bool = False, zip_password: bytes = b'') -> None:
        super().__init__(file_name, content, identifier, force_reprocess, zip_password)
        self.already_exists = False
        self.will_be_processed = False

    def upload(self) -> None:
        logging.info(f'Processing non-zip {self.identifier} file.')
        with transaction.atomic():
            self.already_exists, sample = Sample.objects.get_or_create(self.sha1, self.file_name, self.content, self.identifier)
            self.will_be_processed = self.requires_processing(sample)
            if self.will_be_processed:
                job_id = self._process_sample(sample)
                logging.info(f'File {self.sha1=} sent to the queue with {job_id=}')
            else:
                logging.info(f'File {self.sha1=} is not going to be processed again, because it\'s not needed and it\'s not foced.')

    def _process_sample(self, sample: Sample) -> str:
        _, job_id = RedisManager().submit_sample(sample)
        sample.wipe()  # for reprocessing or non-finished processing.
        RedisJob.objects.create(job_id=job_id, sample=sample)  # assign the new job to the sample
        return job_id