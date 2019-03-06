from collections import OrderedDict
import copy

from .. import Read as Read2
from ...Workflow import Workflow 
from ....operations.SSRL_BEAMLINE_1_5.ReadSpecHeader import ReadSpecHeader 

# NOTE: this workflow is for reading samples
# that were saved with text headers generated by SPEC 

class Read(Read2.Read):

    def __init__(self):
        super(Read,self).__init__(inputs,outputs)
        self.reader = ReadSpecHeader()

    # override the header reader
    def read_header(self,filepath):
        read_outputs = self.reader.run_with(file_path=self.inputs['header_file'])
        return read_outputs['data'] 

