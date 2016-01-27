# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import codecs
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.template.loader import render_to_string
from threading import Thread
import six

import logging
logger = logging.getLogger('cosinnus')


def import_from_settings(name):
    from django.core.exceptions import ImproperlyConfigured
    from django.utils.importlib import import_module
    from cosinnus.conf import settings

    try:
        value = getattr(settings, name, None)
        module_name, _, klass_name = value.rpartition('.')
    except ValueError:
        raise ImproperlyConfigured("%s must be of the form 'path.to.MyClass'" %
                                   name)
    module = import_module(module_name)
    klass = getattr(module, klass_name, None)
    if klass is None:
        raise ImproperlyConfigured("%s does not exist." % klass_name)
    return klass


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        # always use utf-8 to encode, no matter which encoding we decoded while reading
        return self.reader.next().encode("utf-8")
    

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """
    
    _encoding = None

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", delimiter=b',', **kwds):
        f = UTF8Recoder(f, encoding)
        self._encoding = encoding
        self.reader = csv.reader(f, dialect=dialect, delimiter=delimiter, quotechar=b'"', **kwds)

    def next(self):
        row = self.reader.next()
        # utf-8 must be used here because we use a UTF8Reader
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self



class GroupCSVImporter(Thread):
    """ Extend this class to implement the specific import function `do_group_import``! 
        Assign your new class to the setting ``COSINNUS_CSV_IMPORT_GROUP_IMPORTER`` to have it be used for the import. 
        @param group_rows: The rows of CSV imported groups. 
        @param request: Supply a request if a report summary of the import should be mailed to the user """
    
    # mapping from (internal_column_alias --> column-id). only ever access the CSV rows through this map
    # or the self.get() function!
    # this makes it easier to re-configure the import when the CSV changes
    ALIAS_MAP = {}
    
    has_header = False
    
    def __init__(self, rows, request=None, *args, **kwargs):
        self.rows = rows
        self.request = request
        self.item_index = 0
        # a map of { column-header-id: column-index), ... }
        self.column_map = [] if not self.has_header else self._index_and_remove_header_row()
        
        if self.__class__.__name__ == 'GroupCSVImporter':
            raise ImproperlyConfigured('The GroupCSVImporter needs to be extended and requires a ``do_group_import`` function to be implemented!')
        if len(self.ALIAS_MAP) <= 0:
            raise ImproperlyConfigured('No column alias map has been configured. Please define ALIAS_MAP in your class!')
        super(GroupCSVImporter, self).__init__(*args, **kwargs)
    
    def _index_and_remove_header_row(self):
        if len(self.rows) <= 0:
            raise ImproperlyConfigured('The GroupCSVImporter was configured to have a header row, but none could be found!')
        header = self.rows[0]
        self.rows = self.rows[1:]
        column_map = dict([(value.strip(), index) for index, value in enumerate(header)])
        # sanity check if all mapped aliases appear in CSV header
        missing_aliases = [alias for alias in self.ALIAS_MAP.values() if alias not in column_map.keys()]
        if missing_aliases:
            raise ImproperlyConfigured('The GroupCSVImporter was configured to access CSV columns [%s], but they were not found in the CSV header row!' % ', '.join(iterable))
        return column_map
    
    def get(self, internal_column_alias):
        """ Returns the value of the column ``internal_column_alias`` from the current row.
            ``internal_column_alias`` must be defined in ALIAS_MAP. """
        if not internal_column_alias in self.ALIAS_MAP:
            raise ImproperlyConfigured('CSVGroupImporter tried to access a column through unknown column-alias "%s"' % internal_column_alias)
        # retrieve the item via its alias. if there was a header row, retrieve by column-id, else by column-index
        alias_target = self.ALIAS_MAP[internal_column_alias]
        if self.has_header:
            if not alias_target in self.column_map:
                raise ImproperlyConfigured('CSVGroupImporter could not find configured column with header "%s"' % alias_target)
            val = self.rows[self.item_index][self.column_map[alias_target]]
        else:
            val = self.rows[self.item_index][alias_target]
        # set empty values to None unless they are integer zeros
        val = val if val or val == 0 else None
        # trim whitespace
        if isinstance(val, six.string_types):
            val = val.strip()
        return val
    
    def next(self):
        """ Advances to the next CSV item.
            @return: True if there was at least another row in the CSV rows, False if none are left after advancing. """
        self.item_index += 1
        if self.item_index >= len(self.rows):
            return False
        return True
    
    def do_group_import_threaded(self):
        self.start()
    
    def run(self):
        # do not just let the thread die on an exception with no notice
        try:
            self.do_group_import()
        except Exception, e:
            logger.error('An unexpected error in outer import happened! Exception was: %s' % str(e), extra={'exception': e})
            self.import_failed(data={'msg': 'An unexpected error in outer import happened! Exception was: %s' % str(e)})
            
    
    def do_group_import(self):
        pass
    
    def _send_summary_mail(self, template, subj_template, data):
        from cosinnus.core.mail import get_common_mail_context, send_mail_or_fail
        from cosinnus.utils.context_processors import cosinnus as cosinnus_context
        
        receiver = self.request.user
        if self.request:
            context = get_common_mail_context(self.request, user=receiver)
            context.update(cosinnus_context(self.request))
        else:
            context = {} 
        context.update(data)
        subject = render_to_string(subj_template, context)
        send_mail_or_fail(receiver.email, subject, template, context)
    
    def import_finished(self, data):
        if not self.request:
            return
        self._send_summary_mail('cosinnus/mail/csv_import_summary.txt', 'cosinnus/mail/csv_import_summary_subj.txt', data)
    
    def import_failed(self, data):
        if not self.request:
            return
        self._send_summary_mail('cosinnus/mail/csv_import_failed.txt', 'cosinnus/mail/csv_import_failed_subj.txt', data)
    

class EmptyOrUnreadableCSVContent(Exception): pass
class UnexpectedNumberOfColumns(Exception): pass 

def csv_import_projects(csv_file, request=None, encoding="utf-8", delimiter=b',', expected_columns=None):
    """ Imports CosinnusGroups (projects and societies) from a CSV file (InMemory or opened).
        
        @param expected_columns: if set to an integer, each row must have this number of columns,
                                or the import is rejected
        
        @return: (imported_groups, imported_projects, updated_groups, updated_projects): 
             a 4-tuple of groups and projects imported and groups and projects updated 
        @raise UnicodeDecodeError: if the supplied csv_file is not encoded in 'utf-8' """
    
    rows = UnicodeReader(csv_file, encoding=encoding, delimiter=delimiter)
    try:
        # de-iterate to throw encoding errors if there are any
        rows = [row for row in rows]
    except UnicodeDecodeError:
        raise
    
    # sanity check, we require more than 0 rows and more than 1 column 
    # (otherwise we likely decoded with the wrong codec, or delimiter)
    if len(rows) <= 0 or len(rows[0]) <= 1:
        raise EmptyOrUnreadableCSVContent()
    
    # sanity check for expected number of columns, in EACH row
    if expected_columns:
        expected_columns = int(expected_columns)
        if any([len(row) != expected_columns for row in rows]):
            raise UnexpectedNumberOfColumns()
    
    GroupImporter = import_from_settings('COSINNUS_CSV_IMPORT_GROUP_IMPORTER')
    importer = GroupImporter(rows, request=request)
    importer.do_group_import_threaded()
    
    debug = ''
    for row in rows:
        # TODO: import projects from rows
        debug += ' | '.join(row) + ' --<br/><br/>-- '
        
    return debug


