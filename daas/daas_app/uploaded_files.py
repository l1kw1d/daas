import logging
import hashlib
from functools import cached_property
from django.db import transaction

from .models import Sample, RedisJob
from .utils import classifier, zip_distributor
from .utils.redis_manager import RedisManager


class UploadedFile:
    def __init__(self, file_name: str, content: bytes, force_reprocess: bool = False):
        self.content = content
        self.file_name = file_name
        self.force_reprocess = force_reprocess
        self.identifier = classifier.get_identifier_of_file(content)
        self.sha1 = hashlib.sha1(content).hexdigest()

    def requires_processing(self, sample):
        return self.force_reprocess or sample.requires_processing


class Zip(UploadedFile):
    def upload(self):
        logging.info('Processing zip file.')
        return zip_distributor.upload_files_of(self.content)


class NewSample(UploadedFile):
    def upload(self):
        logging.info(f'Processing non-zip {self.identifier} file.')
        with transaction.atomic():
            already_exists, sample = Sample.objects.get_or_create(self.sha1, self.file_name, self.content, self.identifier)
            logging.debug('Sample: %s' % sample)
            if requires_processing := self.requires_processing(sample):
                _, job_id = RedisManager().submit_sample(sample)
                sample.wipe()  # for reprocessing or non-finished processing.
                RedisJob.objects.create(job_id=job_id, sample=sample)  # assign the new job to the sample
                logging.info(f'File {self.sha1} sent to the queue with job_id = {job_id}')
            else:
                logging.info(f'This sample ({self.sha1}) is not going to be processed again, because it\'s not needed and it\'s not foced.')
        return already_exists, requires_processing


class OldSample(UploadedFile):
    pass


class NonSample(UploadedFile):
    pass

