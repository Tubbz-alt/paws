from collections import OrderedDict
from functools import partial
import copy

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
import tkinter
from tkinter import Tk, Frame, Canvas, Button, Label, Entry, \
OptionMenu, Scrollbar, Checkbutton, \
StringVar, DoubleVar, BooleanVar, IntVar
import numpy as np
#from matplotlib import pyplot as plt
#from matplotlib.widgets import Slider, Button, RadioButtons, TextBox
import xrsdkit
from xrsdkit.fitting.xrsd_fitter import XRSDFitter
from ...Operation import Operation

inputs = OrderedDict(
    q_I=None,
    source_wavelength=None,
    populations=None,
    fixed_params=None,
    param_bounds=None,
    param_constraints=None)
outputs = OrderedDict(
    populations=None,
    fixed_params=None,
    param_bounds=None,
    param_constraints=None,
    report=None,
    q_I_opt=None,
    success_flag=False)
        
class XRSDFitGUI(Operation):
    """Interactively fit a XRSD spectrum."""

    # TODO: graceful exit with a call to finish() when the window is closed by force 


    def __init__(self):
        super(XRSDFitGUI, self).__init__(inputs, outputs)
        self.input_doc['q_I'] = 'n-by-2 array of q(1/Angstrom) versus I(arb).'
        self.input_doc['source_wavelength'] = 'wavelength of light source, in Angstroms'
        self.input_doc['populations'] = 'dict defining populations, xrsdkit format'
        self.input_doc['fixed_params'] = 'dict defining fixed params, xrsdkit format'
        self.input_doc['param_bounds'] = 'dict defining param bounds, xrsdkit format'
        self.input_doc['param_constraints'] = 'dict defining param constraints, xrsdkit format'
        self.output_doc['populations'] = 'populations with parameters optimized'
        self.output_doc['fixed_params'] = 'fixed_params after fitting complete'
        self.output_doc['param_bounds'] = 'param_bounds after fitting complete'
        self.output_doc['param_constraints'] = 'param_constraints after fitting complete'
        self.output_doc['report'] = 'dict reporting optimization results'
        self.output_doc['q_I_opt'] = 'computed intensity for the optimized populations'
        self.output_doc['success_flag'] = 'flag indicating user satisfaction with the fit'

    def run(self):
        self.q_I = self.inputs['q_I']
        self.src_wl = self.inputs['source_wavelength']
        self.populations = copy.deepcopy(self.inputs['populations'])
        self.fixed_params = copy.deepcopy(self.inputs['fixed_params'])
        self.param_bounds = copy.deepcopy(self.inputs['param_bounds'])
        self.param_constraints = copy.deepcopy(self.inputs['param_constraints'])
        self.fit_report = None
        self.q_I_opt = None
        self.xrsd_fitter = XRSDFitter(self.q_I,self.populations,self.src_wl)

        self.fit_gui = Tk()
        self.fit_gui.title('xrsd profile fitter')

        scrollbar = Scrollbar(self.fit_gui, orient='horizontal')
        self.fit_gui_canvas = Canvas(self.fit_gui, width=1300, height=730) #background="green"
        scrollbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.fit_gui_canvas.pack(side=tkinter.RIGHT,fill=tkinter.BOTH, expand=tkinter.YES)
        scrollbar.config(command=self.fit_gui_canvas.xview)
        self.fit_gui_canvas.config(scrollregion=(0,0,1300,730), xscrollcommand=scrollbar.set)
        self.main_frame = Frame(self.fit_gui_canvas,bd=4,relief=tkinter.SUNKEN)#, background="green")
        self.window = self.fit_gui_canvas.create_window(0,0,window=self.main_frame, anchor='nw')
        self.fit_gui_canvas.bind("<Configure>", self.onCanvasConfigure)

        # data structures for maintaining refs to widgets
        self.pop_frames = OrderedDict()
        self.param_frames = OrderedDict()
        self.setting_frames = OrderedDict()
        self.site_frames = OrderedDict()
        self.specie_frames = OrderedDict()
        self.specie_setting_frames = OrderedDict()
        self.specie_param_frames = OrderedDict()
        self.new_site_frames = OrderedDict()
        self.new_specie_frames = OrderedDict()
        self.new_pop_frame = None
        self.control_frame = None

        # tkinter vars for entry and display
        self.structure_vars = OrderedDict()
        self.param_vars = OrderedDict()
        self.param_fix_vars = OrderedDict()
        self.param_bound_vars = OrderedDict()
        self.param_constraint_vars = OrderedDict()
        self.setting_vars = OrderedDict()
        self.coordinate_vars = OrderedDict()
        self.coordinate_fix_vars = OrderedDict()
        self.specie_vars = OrderedDict()
        self.specie_param_vars = OrderedDict()
        self.specie_setting_vars = OrderedDict()
        self.new_site_vars = OrderedDict()
        self.new_specie_vars = OrderedDict()
        self.new_pop_var = None
        self.logI_weighted_var = None
        self.error_weighted_var = None
        self.fit_obj_var = None
        self.good_fit_var = None

        # create the plots
        self.build_plot_widgets()

        # create the widgets for population control
        self.build_entry_widgets()


        # start the tk loop
        self.fit_gui.mainloop()

        # after tk loop exits, finish Operation
        #self.finish()

    def onCanvasConfigure(self, event):
        #Resize the inner frame to match the canvas
        minWidth = self.main_frame.winfo_reqwidth()
        minHeight = self.main_frame.winfo_reqheight()

        if self.fit_gui.winfo_width() >= minWidth:
            newWidth = self.fit_gui.winfo_width()
        else:
            newWidth = minWidth
        if self.fit_gui.winfo_height() >= minHeight:
            newHeight = self.fit_gui.winfo_height()
        else:
            newHeight = minHeight
        self.fit_gui_canvas.itemconfigure(self.window, width=newWidth, height=newHeight)

    def get_tk_object_dicts(self):
        all_dicts = [self.pop_frames, \
            self.structure_vars, self.coordinate_vars, self.coordinate_fix_vars, \
            self.param_frames, self.param_vars, \
            self.param_fix_vars, self.param_bound_vars, self.param_constraint_vars, \
            self.setting_frames, self.setting_vars, \
            self.site_frames, \
            self.specie_frames, self.specie_vars, \
            self.specie_param_frames, self.specie_param_vars, \
            self.specie_setting_frames, self.specie_setting_vars, \
            self.new_site_frames, self.new_site_vars, \
            self.new_specie_frames, self.new_specie_vars]
        return all_dicts


    def build_plot_widgets(self):
        self.plot_frame = Frame(self.main_frame,bd=4,relief=tkinter.SUNKEN)#, background="green")
        self.plot_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=tkinter.YES,padx=2,pady=2)

        self.fig = Figure()
        self.fig.set_size_inches(8,7, forward=True)
        self.ax_plot = self.fig.add_subplot(111)

        self.canvas = Canvas(self.plot_frame, width=790)
        #self.plot_frame.bind_all("<MouseWheel>", self.on_mousewheel2)
        #self.plot_frame.bind_all("<Button-4>", self.on_trackpad2)
        #self.plot_frame.bind_all("<Button-5>", self.on_trackpad2)
        yScrollbar = Scrollbar(self.plot_frame)
        yScrollbar.pack(side=tkinter.RIGHT,fill='y')
        self.canvas.pack(fill='both',expand=True)

        self.canvas.config(yscrollcommand=yScrollbar.set)
        yScrollbar.config(command=self.canvas.yview)
        self.plot_canvas = FigureCanvasTkAgg(self.fig,self.canvas)
        self.mplCanvas = self.plot_canvas.get_tk_widget()
        self.cwid = self.canvas.create_window(0, 0, window=self.mplCanvas, anchor='nw')
        #self.canvas.config(scrollregion=self.canvas.bbox('all'))
        self.canvas.config(scrollregion=(0,0,730,730))
        self.canvas.bind("<Configure>", self.onCanvasConfigure2)
        self.draw_plots()

    def onCanvasConfigure2(self, event):
        #Resize the inner frame to match the canvas
        minWidth = self.mplCanvas.winfo_reqwidth()
        minHeight = self.mplCanvas.winfo_reqheight()

        if self.plot_frame.winfo_width() >= minWidth:
            newWidth = self.plot_frame.winfo_width()
        else:
            newWidth = minWidth
        if self.plot_frame.winfo_height() >= minHeight:
            newHeight = self.plot_frame.winfo_height()
        else:
            newHeight = minHeight
        self.canvas.itemconfigure(self.cwid, width=newWidth, height=newHeight)

    def build_entry_widgets(self):
        self.scroll_frame = Frame(self.main_frame)
        self.scroll_frame.pack(side=tkinter.RIGHT,fill='y')
        #self.fit_gui_canvas.create_window(820,0,window=self.scroll_frame, anchor='nw')
        self.pops_canvas = Canvas(self.scroll_frame, width=450)# height=730
        self.scroll_frame.bind_all("<MouseWheel>", self.on_mousewheel)
        self.scroll_frame.bind_all("<Button-4>", self.on_trackpad)
        self.scroll_frame.bind_all("<Button-5>", self.on_trackpad)
        scr = Scrollbar(self.scroll_frame,orient='vertical',command=self.pops_canvas.yview)
        scr.pack(side=tkinter.RIGHT,fill='y')
        self.pops_frame = Frame(self.pops_canvas)
        scroll_canvas_config = lambda ev: self.pops_canvas.configure(scrollregion=self.pops_canvas.bbox("all"))
        self.pops_frame.bind("<Configure>",scroll_canvas_config)
        self.pops_frame.pack(side=tkinter.LEFT,fill='y')
        self.pops_canvas.create_window((0,0),window=self.pops_frame,anchor='nw')
        self.pops_canvas.configure(yscrollcommand=scr.set)
        self.pops_canvas.pack(side=tkinter.LEFT,fill='y')
        self.create_entry_widgets()
        self.create_new_pop_frame()
        self.create_control_frame()

    def on_mousewheel(self, event):
        self.pops_canvas.yview_scroll(-1 * event.delta, 'units')

    #def on_mousewheel2(self, event):
        #self.canvas.yview_scroll(-1 * event.delta, 'units')

    def on_trackpad(self, event):
        if event.num == 4:
            d = -2
        elif event.num == 5:
            d = 2
        self.pops_canvas.yview_scroll(d, 'units')
    '''
    def on_trackpad2(self, event):
        if event.num == 4:
            d = -2
        elif event.num == 5:
            d = 2
        self.canvas.yview_scroll(d, 'units')
    '''

    def finish(self):
        self.outputs['populations'] = self.populations
        self.outputs['fixed_params'] = self.fixed_params
        self.outputs['param_bounds'] = self.param_bounds
        self.outputs['param_constraints'] = self.param_constraints
        self.outputs['report'] = self.fit_report
        self.outputs['q_I_opt'] = self.q_I_opt
        self.outputs['success_flag'] = self.good_fit_var.get()
        self.fit_gui.destroy()

    def draw_plots(self):
        self.ax_plot.clear()
        self.ax_plot.semilogy(self.q_I[:,0],self.q_I[:,1],lw=2,color='black')
        #self.ax_plot.loglog(self.q_I[:,0],self.q_I[:,1],lw=2,color='black')
        I_est = xrsdkit.scattering.compute_intensity(self.q_I[:,0],self.populations,self.src_wl)
        self.ax_plot.semilogy(self.q_I[:,0],I_est,lw=2,color='red')
        #self.ax_plot.loglog(self.q_I[:,0],I_est,lw=2,color='red')
        self.ax_plot.set_xlabel('q (1/Angstrom)')
        self.ax_plot.set_ylabel('Intensity (counts)')
        self.ax_plot.legend(['measured','computed'])
        self.plot_canvas.draw()

    def create_entry_widgets(self):
        self.pop_frames = OrderedDict()
        # create a frame for every population
        for pop_nm in self.populations.keys():
            self.create_pop_frame(pop_nm)

    def create_pop_frame(self,pop_nm):
        popd = self.populations[pop_nm]
        pf = Frame(self.pops_frame,bd=4,pady=10,padx=10,relief=tkinter.RAISED)
        self.pop_frames[pop_nm] = pf

        popl = Label(pf,text='population name:',anchor='e')
        popl.grid(row=0,column=0,sticky=tkinter.E)
        popnml = Label(pf,text=pop_nm,anchor='w')
        popnml.grid(row=0,column=1,sticky=tkinter.W)
        rmb = Button(pf,text='Remove',command=partial(self.remove_population,pop_nm))
        rmb.grid(row=0,column=2)

        strl = Label(pf,text='structure:',width=12,anchor='e')
        strl.grid(row=1,column=0,sticky=tkinter.E)
        strvar = StringVar(pf)
        str_option_dict = OrderedDict.fromkeys(xrsdkit.structure_names)
        strcb = OptionMenu(pf,strvar,*str_option_dict)
        strvar.set(popd['structure'])
        strvar.trace('w',partial(self.update_structure,pop_nm))
        strcb.grid(row=1,column=1,sticky=tkinter.W)
        self.structure_vars[pop_nm] = strvar

        self.create_setting_frames(pop_nm)
        self.create_param_frames(pop_nm)
        self.create_site_frames(pop_nm)
        pf.pack(side=tkinter.TOP,pady=2,padx=2)
        if self.new_pop_frame is not None:
            self.repack_new_pop_frame()
        if self.control_frame is not None:
            self.repack_control_frame()

    def connected_entry(self,parent,tkvar,cbfun=None,entry_width=20):
        if cbfun:
            # piggyback on entry validation
            # to update internal data
            # associated with the entry widget
            # NOTE: validatecommand must return a boolean
            e = Entry(parent,width=entry_width,textvariable=tkvar,validate="focusout",validatecommand=cbfun)
            #e = Entry(parent,width=20,textvariable=tkvar)
            # also respond to the return key
            e.bind('<Return>',cbfun)
        else:
            e = Entry(parent,width=20,textvariable=tkvar)
        return e

    def connected_checkbutton(self,parent,boolvar,cbfun,label=''):
        if cbfun:
            # to update internal data
            # associated with the widget
            e = Checkbutton(parent,text=label,variable=boolvar,command=cbfun)
        else:
            e = Checkbutton(parent,text=label,variable=boolvar)
        return e

    def create_setting_frames(self,pop_nm):
        self.setting_frames[pop_nm] = OrderedDict()
        self.setting_vars[pop_nm] = OrderedDict()
        pf = self.pop_frames[pop_nm]
        popd = self.populations[pop_nm]
        settingsl = Label(pf,text='------- SETTINGS -------')
        settingsl.grid(row=2,column=0,columnspan=3)
        for istg,stg_nm in enumerate(xrsdkit.structure_settings[popd['structure']]):
            stgf = Frame(pf,bd=2,pady=4,padx=10,relief=tkinter.GROOVE)

            if xrsdkit.setting_datatypes[stg_nm] is str:
                stgv = StringVar(pf)
            elif xrsdkit.setting_datatypes[stg_nm] is int:
                stgv = IntVar(pf)
            elif xrsdkit.setting_datatypes[stg_nm] is float:
                stgv = DoubleVar(pf)
            self.setting_frames[pop_nm][stg_nm] = stgf
            self.setting_vars[pop_nm][stg_nm] = stgv

            stgl = Label(stgf,text='{}:'.format(stg_nm),width=12,anchor='e')
            stgl.grid(row=0,column=0,sticky=tkinter.E)
            s = xrsdkit.setting_defaults[stg_nm]
            if stg_nm in popd['settings']:
                s = popd['settings'][stg_nm]
            stgv.set(str(s))
            stge = self.connected_entry(stgf,stgv,partial(self.update_setting,pop_nm,stg_nm,True))
            stge.grid(row=0,column=1,columnspan=2,sticky=tkinter.W)
            stgf.grid(row=3+istg,column=0,columnspan=4,sticky=tkinter.E+tkinter.W)

    def create_param_frames(self,pop_nm):
        self.param_frames[pop_nm] = OrderedDict()
        self.param_vars[pop_nm] = OrderedDict()
        self.param_fix_vars[pop_nm] = OrderedDict()
        self.param_bound_vars[pop_nm] = OrderedDict()
        self.param_constraint_vars[pop_nm] = OrderedDict()
        pf = self.pop_frames[pop_nm]
        popd = self.populations[pop_nm]
        paramsl = Label(pf,text='------ PARAMETERS ------')
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        paramsl.grid(row=3+nstgs,column=0,columnspan=3)
        for ip,param_nm in enumerate(xrsdkit.structure_params[popd['structure']]):
            paramf = Frame(pf,bd=2,pady=4,padx=10,relief=tkinter.GROOVE)
            paramv = DoubleVar(pf)
            p = xrsdkit.param_defaults[param_nm]
            if param_nm in popd['parameters']:
                p = popd['parameters'][param_nm]
            paramv.set(p)
            self.param_frames[pop_nm][param_nm] = paramf
            self.param_vars[pop_nm][param_nm] = paramv

            pl = Label(paramf,text='{}:'.format(param_nm),width=12,anchor='e')
            pl.grid(row=0,column=0,sticky=tkinter.E)
            pe = self.connected_entry(paramf,paramv,partial(self.update_param,pop_nm,param_nm,True))
            pe.grid(row=0,column=1,columnspan=2,sticky=tkinter.W)

            pfixvar = BooleanVar(pf)
            pfx = xrsdkit.fixed_param_defaults[param_nm]
            if xrsdkit.contains_param(self.fixed_params,pop_nm,param_nm):
                pfx = self.fixed_params[pop_nm]['parameters'][param_nm]
            pfixvar.set(pfx)
            self.param_fix_vars[pop_nm][param_nm] = pfixvar
            psw = self.connected_checkbutton(paramf,pfixvar,
                partial(self.update_fixed_param,pop_nm,param_nm),'fixed')

            psw.grid(row=0,column=3,sticky=tkinter.W)
            pbndl = Label(paramf,text='bounds:',width=10,anchor='e')
            pbndl.grid(row=1,column=0,sticky=tkinter.E)
            lbndv = DoubleVar(pf)
            ubndv = DoubleVar(pf)
            lbnd = xrsdkit.param_bound_defaults[param_nm][0]
            ubnd = xrsdkit.param_bound_defaults[param_nm][1]
            if xrsdkit.contains_param(self.param_bounds,pop_nm,param_nm):
                lbnd = self.param_bounds[pop_nm]['parameters'][param_nm][0]
                ubnd = self.param_bounds[pop_nm]['parameters'][param_nm][1]
            if lbnd is None: lbnd = float('inf')
            if ubnd is None: ubnd = float('inf')
            lbndv.set(lbnd)
            ubndv.set(ubnd)
            self.param_bound_vars[pop_nm][param_nm]=[lbndv,ubndv]
            pbnde1 = self.connected_entry(paramf,lbndv,partial(self.update_param_bound,pop_nm,param_nm,0),8)
            pbnde2 = self.connected_entry(paramf,ubndv,partial(self.update_param_bound,pop_nm,param_nm,1),8)
            pbnde1.grid(row=1,column=1,sticky=tkinter.W)
            pbnde2.grid(row=1,column=2,sticky=tkinter.W)

            pexpl = Label(paramf,text='expression:',width=10,anchor='e')
            pexpl.grid(row=2,column=0,sticky=tkinter.E)
            expr = StringVar(pf)
            expr.set("")
            if xrsdkit.contains_param(self.param_constraints,pop_nm,param_nm):
                expr.set(self.param_constraints[pop_nm]['parameters'][param_nm])
            self.param_constraint_vars[pop_nm][param_nm] = expr
            pexpe = self.connected_entry(paramf,expr,partial(self.update_param_constraints,pop_nm,param_nm))
            pexpe.grid(row=2,column=1,columnspan=3,sticky=tkinter.E+tkinter.W)
            paramf.grid(row=4+nstgs+ip,column=0,columnspan=4,sticky=tkinter.E+tkinter.W)

    def create_site_frames(self,pop_nm):
        self.site_frames[pop_nm] = OrderedDict()
        self.new_specie_frames[pop_nm] = OrderedDict()
        self.new_specie_vars[pop_nm] = OrderedDict()
        self.coordinate_vars[pop_nm] = OrderedDict()
        self.coordinate_fix_vars[pop_nm] = OrderedDict()
        self.specie_frames[pop_nm] = OrderedDict()
        self.specie_vars[pop_nm] = OrderedDict()
        self.specie_param_frames[pop_nm] = OrderedDict()
        self.specie_param_vars[pop_nm] = OrderedDict()
        self.specie_setting_frames[pop_nm] = OrderedDict()
        self.specie_setting_vars[pop_nm] = OrderedDict()
        pf = self.pop_frames[pop_nm]
        popd = self.populations[pop_nm]
        npars = len(xrsdkit.structure_params[popd['structure']])
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        basisl = Label(pf,text='--------- BASIS ---------')
        basisl.grid(row=4+nstgs+npars,column=0,columnspan=3)
        for ist,site_nm in enumerate(popd['basis'].keys()):
            self.create_site_frame(pop_nm,site_nm,ist)
        self.create_new_site_frame(pop_nm)

    def create_site_frame(self,pop_nm,site_nm,ist):
        popd = self.populations[pop_nm]
        pf = self.pop_frames[pop_nm]
        npars = len(xrsdkit.structure_params[popd['structure']])
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        sitef = Frame(pf,bd=2,pady=4,padx=10,relief=tkinter.GROOVE)
        self.site_frames[pop_nm][site_nm] = sitef

        stl = Label(sitef,text='site name:',anchor='e')
        stl.grid(row=0,column=0,sticky=tkinter.E)
        stnml = Label(sitef,text=site_nm,anchor='w')
        stnml.grid(row=0,column=1,columnspan=3,sticky=tkinter.W+tkinter.E)
        rmb = Button(sitef,text='Remove',command=partial(self.remove_site,pop_nm,site_nm))
        rmb.grid(row=0,column=4)

        site_def = popd['basis'][site_nm]
        if popd['structure'] in xrsdkit.crystalline_structure_names:
            cvarx = DoubleVar(sitef)
            cvary = DoubleVar(sitef)
            cvarz = DoubleVar(sitef)
            cfixvarx = BooleanVar(sitef)
            cfixvary = BooleanVar(sitef)
            cfixvarz = BooleanVar(sitef)
            self.coordinate_vars[pop_nm][site_nm] = [cvarx,cvary,cvarz]
            self.coordinate_fix_vars[pop_nm][site_nm] = [cfixvarx,cfixvary,cfixvarz]
            coordl = Label(sitef,text='coordinates:',width=12,anchor='e')
            coordfixl = Label(sitef,text='fixed:',width=12,anchor='e')
            coorde1 = self.connected_entry(sitef,cvarx,partial(self.update_coord,pop_nm,site_nm,0),6)
            coorde2 = self.connected_entry(sitef,cvary,partial(self.update_coord,pop_nm,site_nm,1),6)
            coorde3 = self.connected_entry(sitef,cvarz,partial(self.update_coord,pop_nm,site_nm,2),6)
            coordcb1 = self.connected_checkbutton(sitef,cfixvarx,
                partial(self.update_fixed_coord,pop_nm,site_nm,0),'x')
            coordcb2 = self.connected_checkbutton(sitef,cfixvary,
                partial(self.update_fixed_coord,pop_nm,site_nm,1),'y')
            coordcb3 = self.connected_checkbutton(sitef,cfixvarz,
                partial(self.update_fixed_coord,pop_nm,site_nm,2),'z')
            coordl.grid(row=1,column=0,sticky=tkinter.E)
            coorde1.grid(row=1,column=1)
            coorde2.grid(row=1,column=2)
            coorde3.grid(row=1,column=3)
            coordfixl.grid(row=2,column=0,sticky=tkinter.E)
            coordcb1.grid(row=2,column=1)
            coordcb2.grid(row=2,column=2)
            coordcb3.grid(row=2,column=3)
            cdef = xrsdkit.param_defaults['coordinates']
            c = [float(cdef),float(cdef),float(cdef)]
            if 'coordinates' in site_def:
                c = site_def['coordinates']
            cfxdef = xrsdkit.fixed_param_defaults['coordinates']
            cfx = [bool(cfxdef),bool(cfxdef),bool(cfxdef)]
            if xrsdkit.contains_coordinates(self.fixed_params,pop_nm,site_nm):
                cfx = self.fixed_params[pop_nm]['basis'][site_nm]['coordinates'] 
            cvarx.set(c[0])
            cvary.set(c[1])
            cvarz.set(c[2])
            cfixvarx.set(cfx[0])
            cfixvary.set(cfx[1])
            cfixvarz.set(cfx[2])
            # (low priority) TODO: controls for bounding,constraining coords
        else:
            self.coordinate_vars[pop_nm][site_nm] = [None,None,None]
            self.coordinate_fix_vars[pop_nm][site_nm] = [None,None,None]
        self.create_specie_frames(pop_nm,site_nm)
        sitef.grid(row=5+npars+nstgs+ist,column=0,columnspan=4,sticky=tkinter.E+tkinter.W)
        if pop_nm in self.new_site_frames:
            if self.new_site_frames[pop_nm] is not None:
                self.repack_new_site_frame(pop_nm)

    def create_new_site_frame(self,pop_nm):
        pf = self.pop_frames[pop_nm]
        popd = self.populations[pop_nm]
        nsts = len(popd['basis'])
        npars = len(xrsdkit.structure_params[popd['structure']])
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        nsf = Frame(pf,bd=2,pady=10,padx=10,relief=tkinter.GROOVE)
        nsv = StringVar(pf)
        self.new_site_frames[pop_nm] = nsf
        self.new_site_vars[pop_nm] = nsv
        addl = Label(nsf,text='add site:',anchor='e')
        addl.grid(row=0,column=0,sticky=tkinter.E)
        stnme = self.connected_entry(nsf,nsv,None)
        nsv.set(self.default_new_site_name(pop_nm))
        stnme.grid(row=0,column=1,sticky=tkinter.W)
        addb = Button(nsf,text='Add',width=10,command=partial(self.new_site,pop_nm))
        addb.grid(row=0,column=2)
        nsf.grid(row=5+npars+nstgs+nsts,column=0,columnspan=4)

    def repack_new_site_frame(self,pop_nm):
        popd = self.populations[pop_nm]
        nsts = len(popd['basis'])
        npars = len(xrsdkit.structure_params[popd['structure']])
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        self.new_site_frames[pop_nm].pack_forget()
        self.new_site_frames[pop_nm].grid(row=5+npars+nstgs+nsts,column=0,columnspan=4)

    def create_specie_frames(self,pop_nm,site_nm):
        self.specie_frames[pop_nm][site_nm] = OrderedDict()
        self.specie_vars[pop_nm][site_nm] = OrderedDict()
        self.specie_setting_frames[pop_nm][site_nm] = OrderedDict()
        self.specie_setting_vars[pop_nm][site_nm] = OrderedDict()
        self.specie_param_frames[pop_nm][site_nm] = OrderedDict()
        self.specie_param_vars[pop_nm][site_nm] = OrderedDict()
        popd = self.populations[pop_nm]
        site_def = popd['basis'][site_nm]
        row_idx = 0
        for ispec, specie_nm in enumerate(site_def.keys()):
            if not specie_nm == 'coordinates':
                specie_def = site_def[specie_nm]
                if not isinstance(specie_def,list):
                    specie_def = [specie_def]
                for iispec in range(len(specie_def)):
                    self.create_specie_frame(pop_nm,site_nm,specie_nm,row_idx)
                    row_idx += 1
        self.create_new_specie_frame(pop_nm,site_nm)

    def create_specie_frame(self,pop_nm,site_nm,specie_nm,row_idx):
        popd = self.populations[pop_nm]
        site_def = popd['basis'][site_nm]
        iispec = 0
        if specie_nm in self.specie_frames[pop_nm][site_nm]:
            iispec = len(self.specie_frames[pop_nm][site_nm][specie_nm])
        if iispec == 0: 
            self.specie_frames[pop_nm][site_nm][specie_nm] = []
            self.specie_vars[pop_nm][site_nm][specie_nm] = []
            self.specie_param_frames[pop_nm][site_nm][specie_nm] = [OrderedDict()]
            self.specie_param_vars[pop_nm][site_nm][specie_nm] = [OrderedDict()]
            self.specie_setting_frames[pop_nm][site_nm][specie_nm] = [OrderedDict()]
            self.specie_setting_vars[pop_nm][site_nm][specie_nm] = [OrderedDict()]
        else:
            self.specie_param_frames[pop_nm][site_nm][specie_nm].append(OrderedDict())
            self.specie_param_vars[pop_nm][site_nm][specie_nm].append(OrderedDict())
            self.specie_setting_frames[pop_nm][site_nm][specie_nm].append(OrderedDict())
            self.specie_setting_vars[pop_nm][site_nm][specie_nm].append(OrderedDict())
        specie_def = site_def[specie_nm]
        sitef = self.site_frames[pop_nm][site_nm]
        if not isinstance(specie_def,list):
            specie_def = [specie_def]
        specd = specie_def[iispec]
        #for iispec,specd in enumerate(specie_def):
        specf = Frame(sitef,bd=2,padx=10,pady=4,relief=tkinter.GROOVE) 
        specl = Label(specf,text='specie:',width=12,anchor='e')
        specl.grid(row=0,column=0,sticky=tkinter.E)
        specvar = StringVar(sitef)
        spec_option_dict = OrderedDict.fromkeys(xrsdkit.form_factor_names)
        speccb = OptionMenu(specf,specvar,*spec_option_dict)
        specvar.set(specie_nm)
        specvar.trace('w',partial(self.update_specie,pop_nm,site_nm,specie_nm,iispec))
        self.specie_frames[pop_nm][site_nm][specie_nm].append(specf)
        self.specie_vars[pop_nm][site_nm][specie_nm].append(specvar)
        speccb.grid(row=0,column=1,sticky=tkinter.W+tkinter.E)
        rmspecb = Button(specf,text='Remove',command=partial(self.remove_specie,pop_nm,site_nm,specie_nm,iispec))
        rmspecb.grid(row=0,column=2)
        # TODO: connect rmspecb to removing the specie
        self.create_specie_setting_frames(pop_nm,site_nm,specie_nm,iispec)
        self.create_specie_param_frames(pop_nm,site_nm,specie_nm,iispec)
        specf.grid(row=3+row_idx,column=0,columnspan=5,pady=4,sticky=tkinter.E+tkinter.W)
        if pop_nm in self.new_specie_frames:
            if site_nm in self.new_specie_frames[pop_nm]:
                if self.new_specie_frames[pop_nm][site_nm] is not None:
                    self.repack_new_specie_frame(pop_nm,site_nm)
            
    def create_new_specie_frame(self,pop_nm,site_nm):
        sf = self.site_frames[pop_nm][site_nm]
        nspecf = Frame(sf,bd=2,pady=10,padx=10,relief=tkinter.GROOVE)
        nspecv = StringVar(sf)
        self.new_specie_frames[pop_nm][site_nm] = nspecf
        self.new_specie_vars[pop_nm][site_nm] = nspecv
        addl = Label(nspecf,text='add specie:',anchor='e')
        addl.grid(row=0,column=0,sticky=tkinter.E)
        spec_option_dict = OrderedDict.fromkeys(xrsdkit.form_factor_names)
        nspeccb = OptionMenu(nspecf,nspecv,*spec_option_dict)
        nspecv.set('flat')
        nspeccb.grid(row=0,column=1,sticky=tkinter.W)
        addb = Button(nspecf,text='Add',width=10,command=partial(self.new_specie,pop_nm,site_nm))
        addb.grid(row=0,column=2)
        nspec_tot = 0
        for spec_nm,spec_def in self.populations[pop_nm]['basis'][site_nm].items():
            if isinstance(spec_def,list):
                nspec_tot += len(spec_def)
            else:
                nspec_tot += 1
        nspecf.grid(row=4+nspec_tot,column=0,columnspan=4)

    def repack_new_specie_frame(self,pop_nm,site_nm):
        site_def = self.populations[pop_nm]['basis'][site_nm]
        nspec_tot = 0
        for spec_nm,spec_def in site_def.items():
            if isinstance(spec_def,list):
                nspec_tot += len(spec_def)
                print('{} {} at {}'.format(len(spec_def),spec_nm,site_nm))
            else:
                nspec_tot += 1
                print('1 {} at {}'.format(spec_nm,site_nm))
        self.new_specie_frames[pop_nm][site_nm].pack_forget()
        print('{} total species at {}'.format(nspec_tot,site_nm))
        self.new_specie_frames[pop_nm][site_nm].grid(row=4+nspec_tot,column=0,columnspan=4)

    def create_specie_setting_frames(self,pop_nm,site_nm,specie_nm,iispec):
        popd = self.populations[pop_nm]
        site_def = popd['basis'][site_nm]
        specie_def = site_def[specie_nm]
        if not isinstance(specie_def,list):
            specie_def = [specie_def]
        specd = specie_def[iispec]
        specief = self.specie_frames[pop_nm][site_nm][specie_nm][iispec]
        for istg,stg_nm in enumerate(xrsdkit.form_factor_settings[specie_nm]):
            stgf = Frame(specief,bd=2,padx=4,pady=4,relief=tkinter.GROOVE)

            if xrsdkit.setting_datatypes[stg_nm] is str:
                stgv = StringVar(stgf)
            elif xrsdkit.setting_datatypes[stg_nm] is int:
                stgv = IntVar(stgf)
            elif xrsdkit.setting_datatypes[stg_nm] is float:
                stgv = DoubleVar(stgf)

            self.specie_setting_frames[pop_nm][site_nm][specie_nm][iispec][stg_nm] = stgf
            self.specie_setting_vars[pop_nm][site_nm][specie_nm][iispec][stg_nm] = stgv
            stgf.grid(row=1+istg,column=0,columnspan=3,sticky=tkinter.E+tkinter.W)
            stgl = Label(stgf,text='{}:'.format(stg_nm),width=10,anchor='e')
            stgl.grid(row=0,column=0,sticky=tkinter.E)
            #stge = Entry(stgf,width=16,textvariable=stgvar)
            stge = self.connected_entry(stgf,stgv,None)
            stg_val = xrsdkit.setting_defaults[stg_nm]
            if stg_nm in specd: stg_val = specd[stg_nm]
            stgv.set(stg_val)
            stge.grid(row=0,column=1,sticky=tkinter.E+tkinter.W)

    def create_specie_param_frames(self,pop_nm,site_nm,specie_nm,iispec):
        popd = self.populations[pop_nm]
        site_def = popd['basis'][site_nm]
        specie_def = site_def[specie_nm]
        if not isinstance(specie_def,list):
            specie_def = [specie_def]
        specd = specie_def[iispec]
        specief = self.specie_frames[pop_nm][site_nm][specie_nm][iispec]
        nstgs = len(xrsdkit.form_factor_settings[specie_nm])
        for isp,sparam_nm in enumerate(xrsdkit.form_factor_params[specie_nm]):
            sparf = Frame(specief,bd=2,padx=4,pady=4,relief=tkinter.GROOVE)
            spvar = DoubleVar(sparf)
            self.specie_param_frames[pop_nm][site_nm][specie_nm][iispec][sparam_nm] = sparf
            self.specie_param_vars[pop_nm][site_nm][specie_nm][iispec][sparam_nm] = spvar
            sparf.grid(row=1+nstgs+isp,column=0,columnspan=3,sticky=tkinter.E+tkinter.W)
            sparl = Label(sparf,text='{}:'.format(sparam_nm),width=10,anchor='e') # sparam_nm is "occupancy"
            sparl.grid(row=0,column=0,sticky=tkinter.E)
            #spare = Entry(sparf,width=16)
            spare = self.connected_entry(sparf,spvar,None)
            sparam_val = xrsdkit.param_defaults[sparam_nm]
            if sparam_nm in specd: sparam_val = specd[sparam_nm]
            #spare.insert(0,str(sparam_val))
            spvar.set(sparam_val)
            spare.grid(row=0,column=1,columnspan=2,sticky=tkinter.E+tkinter.W)

            sparfxvar = BooleanVar(specief)
            print("sparam_nm", sparam_nm)
            sparfx = xrsdkit.fixed_param_defaults[sparam_nm]
            if xrsdkit.contains_param(self.fixed_params,pop_nm,sparam_nm):
                sparfx = self.fixed_params[pop_nm]['parameters'][sparam_nm]
            sparfxvar.set(sparfx)
            self.param_fix_vars[pop_nm][sparam_nm] = sparfxvar
            sparsw = self.connected_checkbutton(sparf,sparfxvar,
                partial(self.update_fixed_param,pop_nm,sparam_nm),'fixed')
            sparsw.grid(row=0,column=3,sticky=tkinter.W)

            sparbndl = Label(sparf,text='bounds:',width=10,anchor='e')
            sparbndl.grid(row=1,column=0,sticky=tkinter.E)
            sparbnde1 = Entry(sparf,width=8)
            sparbnde2 = Entry(sparf,width=8)
            lbnd = xrsdkit.param_bound_defaults[sparam_nm][0]
            ubnd = xrsdkit.param_bound_defaults[sparam_nm][1]
            # TODO: check for sparam in param_bounds
            sparbnde1.insert(0,str(lbnd))
            sparbnde2.insert(0,str(ubnd))
            sparbnde1.grid(row=1,column=1,sticky=tkinter.W)
            sparbnde2.grid(row=1,column=2,sticky=tkinter.W)
            sparexpl = Label(sparf,text='expression:',width=10,anchor='e')
            sparexpl.grid(row=2,column=0,sticky=tkinter.E)
            sparexpe = Entry(sparf,width=16)
            # TODO: check for sparam in param_constraints
            sparexpe.grid(row=2,column=1,columnspan=3,sticky=tkinter.E+tkinter.W)
            # TODO: connect sparame to setting the param
            # TODO: connect sparsw to changing fixed_params
            # TODO: connect sparbnde to changing param_bounds
            # TODO: connect sparexpe to setting param_constraints


    def new_population(self,event=None):
        new_nm = self.new_pop_var.get()
        if new_nm in self.populations:
            self.new_pop_var.set(self.default_new_pop_name())
        else:
            self.populations[new_nm] = xrsdkit.flat_noise(0.)
            self.create_pop_frame(new_nm)
            self.repack_entry_widgets()

    def new_site(self,pop_nm):
        new_nm = self.new_site_vars[pop_nm].get()
        if new_nm in self.populations[pop_nm]['basis']:
            self.new_site_vars[pop_nm].set(self.default_new_site_name(pop_nm))
        else:
            nsts = len(self.populations[pop_nm]['basis'])
            self.populations[pop_nm]['basis'][new_nm] = {} 
            if self.populations[pop_nm]['structure'] in xrsdkit.crystalline_structure_names:
                cdef = xrsdkit.param_defaults['coordinates']
                self.populations[pop_nm]['basis'][new_nm]['coordinates'] = [float(cdef),float(cdef),float(cdef)] 
            self.create_site_frame(pop_nm,new_nm,nsts)
            self.new_site_vars[pop_nm].set(self.default_new_site_name(pop_nm))
            # no need to draw_plots: this site has no occupant
            #self.draw_plots()
            self.repack_new_site_frame(pop_nm) 

    def new_specie(self,pop_nm,site_nm):
        spec_nm = self.new_specie_vars[pop_nm][site_nm].get()
        site_d = self.populations[pop_nm]['basis'][site_nm] 
        spec_d = xrsdkit.default_specie_definition(spec_nm)
        if spec_nm in site_d:
            if not isinstance(site_d[spec_nm],list):
                site_d[spec_nm] = [site_d[spec_nm]]
            site_d[spec_nm].append(spec_d)
        else:
            site_d[spec_nm] = spec_d
        nspec_tot = 0
        for spnm,spdef in site_d.items():
            if isinstance(spdef,list):
                nspec_tot += len(spdef)
            else:
                nspec_tot += 1
        self.create_specie_frame(pop_nm,site_nm,spec_nm,nspec_tot)
        #self.repack_new_specie_frame(pop_nm,site_nm) 
        self.new_specie_vars[pop_nm][site_nm].set('flat')


    def remove_population(self,pop_nm):
        self.destroy_pop_frame(pop_nm)
        self.populations.pop(pop_nm)
        self.draw_plots()
        self.repack_entry_widgets()

    def remove_site(self,pop_nm,site_nm):
        self.destroy_site_frame(pop_nm,site_nm)
        self.populations[pop_nm]['basis'].pop(site_nm)
        self.draw_plots()
        self.repack_basis_widgets(pop_nm)

    def remove_specie(self,pop_nm,site_nm,specie_nm,iispec):
        self.destroy_specie_frame(pop_nm,site_nm,specie_nm,iispec)
        spec_def = self.populations[pop_nm]['basis'][site_nm][specie_nm]
        if isinstance(spec_def,list):
            spec_def.pop(iispec)
            # TODO (BUG): if iispec is not the end of the list,
            # the remove_specie partial() callbacks will now be mis-indexed.
            # Think of a graceful solution for this,
            # ideally doing away with the iispec arguments altogether.
        else:
            self.populations[pop_nm]['basis'][site_nm].pop(specie_nm)
        self.draw_plots()
        self.repack_site_widgets(pop_nm,site_nm)

    def update_all_population_values(self,new_pops):
        # assume the structure and settings of new_pops
        # will be the same as self.populations.
        for pop_nm,popd in new_pops.items():
            self.update_population_values(pop_nm,popd)
        #self.populations = new_pops
        
    def update_population_values(self,pop_nm,pop_dict):
        for param_nm, param_val in pop_dict['parameters'].items():
            self.update_param_value(pop_nm,param_nm,param_val)
        for site_nm, site_def in pop_dict['basis'].items():
            self.update_site_values(pop_nm,site_nm,site_def)

    def update_param_value(self,pop_nm,param_nm,param_val):
        self.populations[pop_nm]['parameters'][param_nm] = param_val
        self.param_vars[pop_nm][param_nm].set(param_val)

    def update_site_values(self,pop_nm,site_nm,site_def):
        for specie_nm, specie_def in site_def.items():
            self.update_specie_values(pop_nm,site_nm,specie_nm,specie_def)
        # TODO: if crystalline, update coordinate vars

    def update_specie_values(self,pop_nm,site_nm,specie_nm,specie_def):
        if not isinstance(specie_def,list):
            specie_def = [specie_def]
        for ispec,specd in enumerate(specie_def):
            for specie_param_nm,specie_param_val in specd.items():
                self.update_specie_param_value(pop_nm,site_nm,specie_nm,ispec,specie_param_nm,specie_param_val)

    def update_specie_param_value(self,pop_nm,site_nm,specie_nm,ispec,specie_param_nm,specie_param_val):
        spec_def = self.populations[pop_nm]['basis'][site_nm][specie_nm]
        if isinstance(spec_def,list):
            spec_def[ispec][specie_param_nm] = param_val
        else:
            spec_def[specie_param_nm] = specie_param_val
        self.specie_param_vars[pop_nm][site_nm][specie_nm][ispec][specie_param_nm].set(specie_param_val)

    def update_structure(self,pop_nm,var_nm,dummy,mode):
        # updates self.populations to the structure in self.structure_vars
        s = self.structure_vars[pop_nm].get()
        if not s == self.populations[pop_nm]['structure']:
            self.populations[pop_nm]['structure'] = s
            # get default params for the new structure
            new_params = OrderedDict.fromkeys(xrsdkit.structure_params[s])
            for pnm in new_params: new_params[pnm] = xrsdkit.param_defaults[pnm]
            self.populations[pop_nm]['parameters'] = new_params
            # get default settings for the new structure
            new_settings = OrderedDict.fromkeys(xrsdkit.structure_settings[s])
            for snm in new_settings: new_settings[snm] = xrsdkit.setting_defaults[snm]
            self.populations[pop_nm]['settings'] = new_settings

            # if the new structure is crystalline, ensure coordinates are set
            # and ensure that noncrystalline form factors are not present
            new_basis = self.populations[pop_nm]['basis']
            for site_nm, site_def in new_basis.items():
                if s in xrsdkit.crystalline_structure_names:
                    if not 'coordinates' in site_def:
                        site_def['coordinates'] = [0.,0.,0.]
                    for specnm in xrsdkit.noncrystalline_ff_names:
                        if specnm in site_def:
                            site_def.pop(specnm)
                else:
                    if 'coordinates' in site_def:
                        site_def.pop('coordinates')

            self.destroy_setting_frames(pop_nm)
            self.destroy_param_frames(pop_nm)
            self.destroy_site_frames(pop_nm)
            self.create_setting_frames(pop_nm)
            self.create_param_frames(pop_nm)
            self.create_site_frames(pop_nm)
            #self.destroy_pop_frame(pop_nm)
            #self.create_pop_frame(pop_nm)
            self.draw_plots()

    def update_specie(self,pop_nm,site_nm,specie_nm,iispec,var_nm,dummy,mode):
        snm = self.specie_vars[pop_nm][site_nm][specie_nm][iispec].get()
        if not snm == specie_nm:
            site_def = self.populations[pop_nm]['basis'][site_nm]
            # first, remove the old specie from self.populations
            if isinstance(site_def[specie_nm],list):
                site_def[specie_nm].pop(iispec)
            else:
                site_def.pop(specie_nm)
            # create new specie with default settings and parameters
            specie_def = xrsdkit.default_specie_definition(specie_nm) 
            # add the new specie 
            if snm in site_def:
                #ispec = site_def.keys().index(snm)
                if not isinstance(site_def[snm],list):
                    site_def[snm] = [site_def[snm]]
                iispec = len(site_def[snm])
                site_def[snm].append(specie_def)
            else:
                site_def[snm] = specie_def 
                iispec = 0
            #self.destroy_specie_frame(pop_nm,site_nm,specie_nm,iispec)
            #self.create_specie_frame(pop_nm,site_nm,snm,ispec,iispec)
            self.destroy_specie_setting_frames(pop_nm,site_nm,snm,iispec)
            self.destroy_specie_param_frames(pop_nm,site_nm,snm,iispec)
            self.create_specie_setting_frames(pop_nm,site_nm,snm,iispec)
            self.create_specie_param_frames(pop_nm,site_nm,snm,iispec)

    def update_setting(self,pop_nm,stg_nm,draw_plots=False,event=None):
        s_old = self.populations[pop_nm]['settings'][stg_nm]
        is_valid = True
        try:
            s = self.setting_vars[pop_nm][stg_nm].get()
        except:
            is_valid = False
        if is_valid:
            self.populations[pop_nm]['settings'][stg_nm] = s
            if draw_plots:
                self.draw_plots()
        else:
            self.setting_vars[pop_nm][stg_nm].set(s_old)
        return is_valid

    def validate_and_update(self,parent,item_key,old_val,tkvar,draw_plots=False):
        """Validate a Var entry and set its value in a parent data structure

        If the entry is valid, the value is set in `parent` at `item_key`.
        If the entry is not valid, the `tkvar` is reset to `old_val`.
        
        Parameters
        ----------
        parent : object
            A data structure
        item_key : object
            A key for fetching an item from `parent`
        old_val : object
            A value to fall back on if the Var fails to get()
        tkvar : tk.Variable
            The tkinter Variable to get() the new value from

        Returns
        -------
        is_valid : boolean
            Flag for whether or not the entry was found to be valid
        """
        is_valid = True
        try:
            new_val = tkvar.get()
        except:
            is_valid = False
        if is_valid:
            if not new_val == old_val: 
                parent[item_key] = new_val 
                if draw_plots:
                    self.draw_plots()
        else:
            tkvar.set(old_val)
        return is_valid

    def update_param(self,pop_nm,param_nm,draw_plots=False,event=None):
        params = self.populations[pop_nm]['parameters']
        p_old = params[param_nm]
        p_var = self.param_vars[pop_nm][param_nm]
        return self.validate_and_update(params,param_nm,p_old,p_var,draw_plots)

    def update_param_bound(self,pop_nm,param_nm,bound_idx,draw_plots=False,event=None):
        bounds = copy.deepcopy(xrsdkit.param_bound_defaults[param_nm])
        if xrsdkit.contains_param(self.param_bounds,pop_nm,param_nm):
            bounds = self.param_bounds[pop_nm]['parameters'][param_nm]
        b_old = bounds[bound_idx]
        b_var = self.param_bound_vars[pop_nm][param_nm][bound_idx]
        is_valid = self.validate_and_update(bounds,bound_idx,b_old,b_var,False)
        if is_valid:
            xrsdkit.update_param(self.param_bounds,pop_nm,param_nm,bounds)
            # TODO: check the value of the param- if it is outside the bounds, update it and draw_plots.
        return is_valid

    def update_fixed_param(self,pop_nm,param_nm,event=None):
        fp = {} 
        fx_old = bool(xrsdkit.fixed_param_defaults[param_nm])
        if xrsdkit.contains_param(self.fixed_params,pop_nm,param_nm):
            fp = self.fixed_params[pop_nm]['parameters']
            fx_old = fp[param_nm]
        fx_var = self.param_fix_vars[pop_nm][param_nm]
        is_valid = self.validate_and_update(fp,param_nm,fx_old,fx_var,False)
        if is_valid:
            xrsdkit.update_param(self.fixed_params,pop_nm,param_nm,fp[param_nm])
        return is_valid

    def update_param_constraints(self,pop_nm,param_nm,draw_plots=False,event=None):
        pc = {}
        pc_old = None
        if xrsdkit.contains_param(self.param_constraints,pop_nm,param_nm):
            pc = self.param_constraints[pop_nm]['parameters']
            pc_old = pc[param_nm]
        pc_var = self.param_constraint_vars[pop_nm][param_nm]
        is_valid = self.validate_and_update(pc,param_nm,pc_old,pc_var,False)
        # TODO: any additional validation of the constraint expression?
        if is_valid:
            xrsdkit.update_param(self.param_constraints,pop_nm,param_nm,pc[param_nm])
            # TODO: check the value of the param- if violates constraints, update it and draw_plots.
        return is_valid

    def update_coord(self,pop_nm,site_nm,coord_idx,draw_plots=False,event=None):
        coords = self.populations[pop_nm]['basis'][site_nm]['coordinates']
        c_old = coords[coord_idx]
        c_var = self.coordinate_vars[pop_nm][site_nm][coord_idx]
        return self.validate_and_update(coords,coord_idx,c_old,c_var,draw_plots)

    def update_fixed_coord(self,pop_nm,site_nm,coord_idx,event=None):
        fcdef = bool(xrsdkit.fixed_param_defaults['coordinates'])
        fc = [bool(fcdef),bool(fcdef),bool(fcdef)] 
        if xrsdkit.contains_coordinates(self.fixed_params,pop_nm,site_nm):
            fc = self.fixed_params[pop_nm]['basis'][site_nm]['coordinates']
        fc_old = fc[coord_idx]
        fc_var = self.coordinate_fix_vars[pop_nm][site_nm][coord_idx]
        is_valid = self.validate_and_update(fc,coord_idx,fc_old,fc_var,False)
        if is_valid:
            xrsdkit.update_coordinates(self.fixed_params,pop_nm,site_nm,fc)
        return is_valid

    def fit(self):
        ftr = xrsdkit.fitting.xrsd_fitter.XRSDFitter(self.q_I,self.populations,self.src_wl)
        logIwtd = bool(self.logI_weighted_var.get())
        erwtd = bool(self.error_weighted_var.get())
        p_opt,rpt = ftr.fit(self.fixed_params,self.param_bounds,self.param_constraints,erwtd,logIwtd)
        self.fit_obj_var.set(rpt['final_objective'])
        self.update_all_population_values(p_opt)
        self.draw_plots()

    def compute_objective(self):
        ftr = xrsdkit.fitting.xrsd_fitter.XRSDFitter(self.q_I,self.populations,self.src_wl)
        erwtd = bool(self.error_weighted_var.get())
        logIwtd = bool(self.logI_weighted_var.get())
        return ftr.evaluate_residual(self.populations,erwtd,logIwtd)

    def repack_new_pop_frame(self):
        self.new_pop_frame.pack_forget()
        self.new_pop_frame.pack(side=tkinter.TOP,pady=2,padx=2, fill="both", expand=True)

    def repack_control_frame(self):
        self.control_frame.pack_forget()
        self.control_frame.pack(side=tkinter.TOP, pady=2,padx=2, fill="both", expand=True)

    def create_new_pop_frame(self):
        npf = Frame(self.pops_frame,bd=4,pady=10,padx=10,relief=tkinter.RAISED)
        self.new_pop_frame = npf
        npf.pack(side=tkinter.TOP,pady=2,padx=2, fill="both", expand=True)
        addl = Label(npf,text='add population:',anchor='e')
        addl.grid(row=0,column=0,sticky=tkinter.E)
        self.new_pop_var = StringVar(self.pops_frame)
        nme = self.connected_entry(npf,self.new_pop_var,None)
        nme.grid(row=0,column=1,sticky=tkinter.W)
        addb = Button(npf,text='Add',width=10,command=self.new_population)
        addb.grid(row=0,column=2)

    def default_new_pop_name(self):
        ipop = 0
        nm = 'pop_'+str(ipop)
        while nm in self.populations:
            ipop += 1
            nm = 'pop_'+str(ipop)
        return nm

    def default_new_site_name(self,pop_nm):
        ist = 0
        nm = 'site_'+str(ist)
        while nm in self.populations[pop_nm]['basis']:
            ist += 1
            nm = 'site_'+str(ist)
        return nm

    def create_control_frame(self):
        cf = Frame(self.pops_frame,bd=4,pady=10,padx=10,relief=tkinter.RAISED)
        self.control_frame = cf
        self.fit_obj_var = StringVar(cf)
        self.error_weighted_var = BooleanVar(cf)
        self.logI_weighted_var = BooleanVar(cf)
        objl = Label(cf,text='objective:',anchor='e')
        objl.grid(row=0,column=0,rowspan=2,sticky=tkinter.E)
        rese = Entry(cf,width=20,state='readonly',textvariable=self.fit_obj_var)
        rese.grid(row=0,column=1,rowspan=2,sticky=tkinter.W)
        self.fit_obj_var.set(str(self.compute_objective()))
        self.error_weighted_var = BooleanVar(cf)
        ewtcb = Checkbutton(cf,text="error weighted",variable=self.error_weighted_var)
        ewtcb.select()
        ewtcb.grid(row=0,column=2,sticky=tkinter.W)
        self.logI_weighted_var = BooleanVar(cf)
        logwtbox = Checkbutton(cf,text="log(I) weighted",variable=self.logI_weighted_var)
        logwtbox.select()
        logwtbox.grid(row=1,column=2,sticky=tkinter.W)
        fitbtn = Button(cf,text='Fit',width=10,command=self.fit)
        fitbtn.grid(row=2,column=0)
        finbtn = Button(cf,text='Finish',width=10,command=self.finish)
        finbtn.grid(row=2,column=1)
        self.good_fit_var = tkinter.BooleanVar(cf)
        fitcb = Checkbutton(cf,text="Good fit", variable=self.good_fit_var)
        fitcb.grid(row=2,column=2,sticky=tkinter.W)
        cf.pack(side=tkinter.TOP,pady=2,padx=2,fill="both",expand=True)

    def repack_entry_widgets(self):
        for ipop,pop_nm in enumerate(self.populations.keys()):
            pf = self.pop_frames[pop_nm]
            pf.pack_forget()
            pf.pack(side=tkinter.TOP,pady=2,padx=2)
            self.repack_basis_widgets(pop_nm)
        self.repack_new_pop_frame()
        self.repack_control_frame()

    def repack_basis_widgets(self,pop_nm):
        popd = self.populations[pop_nm]
        npars = len(xrsdkit.structure_params[popd['structure']])
        nstgs = len(xrsdkit.structure_settings[popd['structure']])
        for ist,site_nm in enumerate(popd['basis'].keys()):
            sitef = self.site_frames[pop_nm][site_nm]
            sitef.pack_forget()
            sitef.grid(row=5+npars+nstgs+ist,column=0,columnspan=4,sticky=tkinter.E+tkinter.W)
            self.repack_site_widgets(pop_nm,site_nm)

    def repack_site_widgets(self,pop_nm,site_nm):
        popd = self.populations[pop_nm]
        site_def = popd['basis'][site_nm]
        for ispec, specie_nm in enumerate(site_def.keys()):
            if not specie_nm == 'coordinates':
                specie_def = site_def[specie_nm]
                if not isinstance(specie_def,list):
                    specie_def = [specie_def]
                for iispec,specd in enumerate(specie_def):
                    specf = self.specie_frames[pop_nm][site_nm][specie_nm][iispec]
                    specf.pack_forget()
                    specf.grid(row=2+ispec+iispec,column=0,columnspan=5,pady=4,sticky=tkinter.E+tkinter.W)
        self.repack_new_site_frame(pop_nm)

    #def destroy_entry_widgets(self):
    #    pop_nm_list = list(self.pop_frames.keys())
    #    for pop_nm in pop_nm_list:
    #        self.destroy_pop_frame(pop_nm)
    #        self.structure_vars.pop(pop_nm)
    #    self.repack_new_pop_frame()
    #    self.repack_control_frame()

    def destroy_pop_frame(self,pop_nm):
        self.destroy_setting_frames(pop_nm)
        self.destroy_param_frames(pop_nm)
        self.destroy_site_frames(pop_nm)
        popfrm = self.pop_frames.pop(pop_nm)
        popfrm.pack_forget()
        popfrm.destroy()

    def destroy_setting_frames(self,pop_nm):
        for setting_nm in list(self.setting_frames[pop_nm].keys()):
            self.setting_vars[pop_nm].pop(setting_nm)
            setting_frm = self.setting_frames[pop_nm].pop(setting_nm)
            setting_frm.pack_forget()
            setting_frm.destroy()

    def destroy_param_frames(self,pop_nm):
        param_nm_list = list(self.param_frames[pop_nm].keys())
        for param_nm in param_nm_list:
            self.param_vars[pop_nm].pop(param_nm)
            self.param_fix_vars[pop_nm].pop(param_nm) 
            self.param_bound_vars[pop_nm].pop(param_nm)  
            param_frm = self.param_frames[pop_nm].pop(param_nm)
            param_frm.pack_forget()
            param_frm.destroy()

    def destroy_site_frames(self,pop_nm):
        site_nm_list = list(self.site_frames[pop_nm].keys())
        for site_nm in site_nm_list:
            self.destroy_site_frame(pop_nm,site_nm)
        self.destroy_new_site_frame(pop_nm)

    def destroy_new_site_frame(self,pop_nm):
        site_frm = self.new_site_frames.pop(pop_nm)
        site_frm.pack_forget()
        site_frm.destroy()

    def destroy_site_frame(self,pop_nm,site_nm):
        self.destroy_specie_frames(pop_nm,site_nm)
        site_frm = self.site_frames[pop_nm].pop(site_nm)
        site_frm.pack_forget()
        site_frm.destroy()

    def destroy_specie_frames(self,pop_nm,site_nm):
        specie_nm_list = list(self.specie_frames[pop_nm][site_nm].keys())
        for specie_nm in specie_nm_list:
            specie_frms = self.specie_frames[pop_nm][site_nm][specie_nm]
            for iispec in range(len(specie_frms))[::-1]:
                self.destroy_specie_frame(pop_nm,site_nm,specie_nm,iispec)

    def destroy_specie_frame(self,pop_nm,site_nm,specie_nm,iispec):
        self.destroy_specie_setting_frames(pop_nm,site_nm,specie_nm,iispec)
        self.destroy_specie_param_frames(pop_nm,site_nm,specie_nm,iispec)
        specie_frm = self.specie_frames[pop_nm][site_nm][specie_nm].pop(iispec)
        specie_frm.pack_forget()
        specie_frm.destroy()

    def destroy_specie_setting_frames(self,pop_nm,site_nm,specie_nm,iispec):
        stg_frms = self.specie_setting_frames[pop_nm][site_nm][specie_nm][iispec]
        stg_nm_list = list(self.specie_setting_frames[pop_nm][site_nm][specie_nm][iispec].keys())
        for stg_nm in stg_nm_list:
            stg_frm = stg_frms.pop(stg_nm)
            stg_frm.pack_forget()
            stg_frm.destroy()

    def destroy_specie_param_frames(self,pop_nm,site_nm,specie_nm,iispec):
        sparam_frms = self.specie_param_frames[pop_nm][site_nm][specie_nm][iispec]
        sparam_nm_list = list(self.specie_param_frames[pop_nm][site_nm][specie_nm][iispec].keys())
        for sparam_nm in sparam_nm_list:
            sparam_frm = sparam_frms.pop(sparam_nm)
            sparam_frm.pack_forget()
            sparam_frm.destroy()
