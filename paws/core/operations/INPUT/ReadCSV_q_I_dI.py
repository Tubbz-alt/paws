import numpy as np

from ..operation import Operation
from ..import optools

class ReadCSV_q_I_dI(Operation):
    """
    Read q, I, and (if available) dI from a csv-formatted file.
    If the csv has no third column, returns None for dI.
    """

    def __init__(self):
        input_names = ['path']
        output_names = ['q','I', 'dI']
        super(ReadCSV_q_I_dI, self).__init__(input_names, output_names)
        self.input_doc['path'] = "path to .csv file"
        self.output_doc['q'] = "1d array, first column of csv, presumed to be scattering vector q"
        self.output_doc['I'] = "1d array, second column of csv, presumed to be scattering intensity I"
        self.output_doc['dI'] = "1d array, third column of csv, presumed to be error estimate of I"
        # source & type
        self.input_src['path'] = optools.fs_input
        self.input_type['path'] = optools.path_type

    def run(self):
        path = self.inputs['path']
        q = np.loadtxt(path, dtype=float, delimiter=',', skiprows=1, usecols=(0,))
        I = np.loadtxt(path, dtype=float, delimiter=',', skiprows=1, usecols=(1,))
        try:
            dI = np.loadtxt(path, dtype=float, delimiter=',', skiprows=1, usecols=(2,))
        except:
            dI = None
        self.outputs['q'] = q
        self.outputs['I'] = I
        self.outputs['dI'] = dI

