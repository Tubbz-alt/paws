from collections import OrderedDict
import os

import fabio

from ...Operation import Operation

inputs=OrderedDict(file_path=None)
outputs=OrderedDict(
    image_data=None,
    FabioImage=None,
    dir_path=None,
    filename=None)

class FabIOOpen(Operation):
    """
    Takes a filesystem path and calls fabIO to load it. 
    """

    def __init__(self):
        super(FabIOOpen,self).__init__(inputs,outputs) 
        self.input_doc['file_path'] = 'string representing the path to a .tif image'
        self.output_doc['image_data'] = '2D array representing pixel values taken from the input file'
        self.output_doc['FabioImage'] = 'The object generated by fabio.open()'
        self.output_doc['dir_path'] = 'Path to the directory the image came from'
        self.output_doc['filename'] = 'The image filename, no path, no extension'
        
    def run(self):
        p = self.inputs['file_path']
        dir_path = os.path.split(p)[0]
        file_nopath = os.path.split(p)[1]
        file_noext = os.path.splitext(file_nopath)[0]
        self.outputs['dir_path'] = dir_path 
        self.outputs['filename'] = file_noext 
        self.message_callback('reading {}'.format(p))
        self.outputs['FabioImage'] = fabio.open(p)
        self.outputs['image_data'] = self.outputs['FabioImage'].data

