import os
from collections import OrderedDict
from threading import Condition

import numpy as np
import pyFAI

from .PawsPlugin import PawsPlugin

content = OrderedDict(calib_file=None) 

class PyFAIIntegrator(PawsPlugin):
    """Plugin for applying a PyFAI.AzimuthalIntegrator.

    Input calibration file should be in one of the formats
    outlined in the package documentation. 
    """
    def __init__(self):
        super(PyFAIIntegrator,self).__init__(content)
        self.content_doc['calib_file'] = 'file defining a dict of calibration parameters, '\
            'in one of the formats outlined in the package documentation'
        self.integrator_lock = Condition()
        self.integrator = None

    def start(self):
        super(PyFAIIntegrator,self).start()
        with self.integrator_lock:
            self.integrator = pyFAI.AzimuthalIntegrator()
        self.set_calib()

    def set_calib_file(self,file_path):
        self.content['calib_file'] = file_path
        #self.set_calib()

    def set_calib(self):
        calib = self.content['calib_file']
        fp,xt = os.path.splitext(calib)
        #print(xt)
        if xt in ['.poni','.PONI']:
            #g = pyFAI.geometry.Geometry()
            #g.read(calib)
            #p.setPyFAI(g.getPyFAI())
            with self.integrator_lock:
                self.integrator.read(calib)
        elif xt in ['.nika','.NIKA']:
            with self.integrator_lock:
                self.set_nika(calib)

    def integrate_to_1d(self,img_data,npt=1000,polz_factor=0.,unit='q_A^-1'):
        with self.integrator_lock:
            q,I = self.integrator.integrate1d(img_data,npt,
                polarization_factor=polz_factor,unit=unit)
        return q,I

    def integrate_to_2d(self,img_data,npt_rad=1000,npt_azim=1000,polz_factor=0.,unit='q_A^-1'):
        with self.integrator_lock:
            I_at_q_chi,q,chi = self.integrator.integrate2d(img_data,
                npt_rad,npt_azim,polarization_factor=polz_factor,unit=unit)
        return q,chi,I_at_q_chi

    def set_nika(self,nika_file):
        # TODO: make nika format yaml-able
        for line in open(nika_file,'r'):
            kv = line.strip().split('=')
            if 'sample_to_CCD_mm' in kv[0]:
                d_mm = float(kv[1])
            if 'pixel_size_x_mm' in kv[0]:
                pxsz_x_mm = float(kv[1])
            if 'pixel_size_y_mm' in kv[0]:
                pxsz_y_mm = float(kv[1])
            if 'beam_center_x_pix' in kv[0]:
                bcx_px = float(kv[1])       # Nika reports the x coord relative to 'bottom left' corner of detector
                                            # where beam axis intersects detector plane, in pixels 
            if 'beam_center_y_pix' in kv[0]:
                bcy_px = float(kv[1])       # same as beam_center_x_pix but for y 
            if 'horizontal_tilt_deg' in kv[0]:    
                htilt_deg = float(kv[1])    # Nika reports the horizontal tilt in degrees...
            if 'vertical_tilt_deg' in kv[0]:
                vtilt_deg = float(kv[1])    # Nika reports the vertical tilt in degrees...
            if 'wavelength_A' in kv[0]:
                wl_A = float(kv[1])         # Nika reports wavelength is in Angstroms
        wl_m = wl_A*1E-10
        pxsz_x_um = pxsz_x_mm * 1000
        pxsz_y_um = pxsz_y_mm * 1000
        # TODO: check whether these rotation angle mappings are correct,
        # going from nika to fit2D geometry. 
        tilt_deg = -1.*htilt_deg
        rot_fit2d = vtilt_deg
        #tmpint = pyFAI.AzimuthalIntegrator(wavelength = wl_m)
        #tmpint.setFit2D(d_mm,bcx_px,bcy_px,tilt_deg,rot_fit2d,pxsz_x_um,pxsz_y_um)
        #pd = tmpint.getPyFAI()
        #self.integrator.setPyFAI(**pd)
        self.integrator.set_wavelength(wl_m)
        self.integrator.setFit2D(d_mm,bcx_px,bcy_px,tilt_deg,rot_fit2d,pxsz_x_um,pxsz_y_um)

    def get_plugin_content(self):
        d = super(PyFAIIntegrator,self).get_plugin_content()
        d['integrator'] = self.integrator 
        return d


