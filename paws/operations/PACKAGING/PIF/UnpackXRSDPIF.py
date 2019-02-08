from collections import OrderedDict

from xrsdkit.tools import piftools

from ...Operation import Operation

inputs=OrderedDict(pif=None)
outputs=OrderedDict(
    experiment_id=None,
    t_utc=None,
    q_I=None,
    temperature=None,
    features=None,
    system=None)

class UnpackXRSDPIF(Operation):
    """Unpack a PIF record that was generated by xrsdkit"""

    def __init__(self):
        super(UnpackXRSDPIF,self).__init__(inputs,outputs)
        self.input_doc['pif'] = 'pif object to be unpacked'
        self.output_doc['experiment_id'] = 'string experiment id'
        self.output_doc['t_utc'] = 'time in seconds utc'
        self.output_doc['q_I'] = 'n-by-2 array of q values and measured saxs intensities'
        self.output_doc['temperature'] = 'temperature in degrees C'
        self.output_doc['features'] = 'dict of numerical features of `q_I`'
        self.output_doc['system'] = 'xrsdkit.system.System object'

    def run(self):
        pp = self.inputs['pif']

        _uid, sys, q_I, expt_id, t_utc, T_C, _src_wl, feats, _cls_labels, _reg_labels = piftools.unpack_pif(pp)

        self.outputs['experiment_id'] = expt_id 
        self.outputs['t_utc'] = t_utc 
        self.outputs['q_I'] = q_I 
        self.outputs['temperature'] = T_C 
        self.outputs['features'] = feats 
        self.outputs['system'] = sys 
