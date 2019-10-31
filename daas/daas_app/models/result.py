from django.db import models
import logging
from django.db.models import Max

from ..utils import result_status
from ..utils.configuration_manager import ConfigurationManager
from .sample import Sample


class ResultQuerySet(models.QuerySet):

    def failed(self):
        return self.filter(status=result_status.FAILED)

    def decompiled(self):
        return self.filter(status=result_status.SUCCESS)

    def timed_out(self):
        return self.filter(status=result_status.TIMED_OUT)

    def max_elapsed_time(self):
        max_elapsed_time = self.decompiled().aggregate(Max('elapsed_time'))['elapsed_time__max']
        return max_elapsed_time if max_elapsed_time is not None else 0


class Result(models.Model):
    class Meta:
        permissions = (('update_statistics_permission', 'Update Statistics'),)

    timeout = models.SmallIntegerField(default=None, blank=True, null=True)
    elapsed_time = models.PositiveSmallIntegerField(default=None, blank=True, null=True)
    exit_status = models.SmallIntegerField(default=None, blank=True, null=True)
    status = models.PositiveSmallIntegerField(db_index=True)  # fixme: usar choices y charfield
    output = models.CharField(max_length=10100)
    compressed_source_code = models.BinaryField(default=None, blank=True, null=True)
    decompiler = models.CharField(max_length=100)
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE)
    processed_on = models.DateTimeField(auto_now_add=True)
    version = models.SmallIntegerField(default=0)
    extension = models.CharField(max_length=15)

    objects = ResultQuerySet.as_manager()

    def save(self, *args, **kwargs):
        # In some strange cases the output was extremely long and higher the limit.
        if len(self.output) > 10100:
            logging.debug('Truncating decompiler output. It is too long.')
            self.output = self.output[:10000] + '\n\n[[[ Output truncated (more than 10000 characters) ]]]'
        super().save(*args, **kwargs)

    @property
    def timed_out(self):
        return self.status == result_status.TIMED_OUT

    @property
    def failed(self):
        return self.status == result_status.FAILED

    @property
    def decompiled(self):
        return self.status == result_status.SUCCESS

    @property
    def file_type(self):
        return self.sample.file_type

    @property
    def get_config(self):
        return ConfigurationManager().get_configuration(self.file_type)

    @property
    def decompiled_with_latest_version(self):
        return self.version == self.get_config.version
