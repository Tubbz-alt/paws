from collections import OrderedDict
import copy
from functools import partial

from PySide import QtCore

from ..treemodel import TreeSelectionModel
from ..treeitem import TreeItem
from ..operations import optools
from ..operations.operation import Operation, Batch, Realtime
from .wf_worker import WfWorker


class Workflow(TreeSelectionModel):
    """
    Tree structure for a workflow built from paws Operations.
    """

    def __init__(self,wfman):
        super(Workflow,self).__init__()
        self._running = False
        self.wfman = wfman

    exec_finished = QtCore.Signal()

    @QtCore.Slot(str,Operation)
    def updateOperation(self,tag,op):
        self.update_op(tag,op)
        # after updating an operation, best processEvents()
        # so that the application can execute anything in the update
        # that was queued in the main event loop.
        self.wfman.appref.processEvents()
        
    def load_inputs(self,op):
        """
        Loads input data for an Operation from that Operation's input_locators.
        It is expected that op.input_locator[name] will refer to an InputLocator.
        """
        for name,il in op.input_locator.items():
            if isinstance(il,optools.InputLocator):
                il.data = self.locate_input(il)
                op.inputs[name] = il.data
            else:
                msg = '[{}] Found broken Operation.input_locator for {}: {}'.format(
                __name__, name, il)
                raise ValueError(msg)

    def locate_input(self,il):
        """
        Return the data pointed to by a given InputLocator object.
        """
        if il.src == optools.no_input or il.tp == optools.none_type:
            return None
        elif il.src == optools.batch_input:
            # Expect this input to have been set by self.set_op_input_at_uri().
            return il.data 
        elif il.src == optools.text_input: 
            if isinstance(il.val,list):
                return [optools.cast_type_val(il.tp,v) for v in il.val]
            else:
                return optools.cast_type_val(il.tp,il.val)
        elif il.src == optools.wf_input:
            if il.tp == optools.ref_type:
                # Note, this will return whatever data is stored in the TreeItem at uri.
                # If il.val is the uri of an input that has not yet been loaded,
                # this means it will get the InputLocator that currently inhabits that uri.
                if isinstance(il.val,list):
                    return [self.get_from_uri(v)[0].data for v in il.val]
                else:
                    return self.get_from_uri(il.val)[0].data
            elif il.tp == optools.path_type: 
                if isinstance(il.val,list):
                    return [str(v) for v in il.val]
                else:
                    return str(il.val)
        elif il.src == optools.plugin_input:
            if il.tp == optools.ref_type:
                if isinstance(il.val,list):
                    return [self.plugman.get_from_uri(v)[0].data for v in il.val]
                else:
                    return self.plugman.get_from_uri(il.val)[0].data
            elif il.tp == optools.path_type:
                if isinstance(il.val,list):
                    return [str(v) for v in il.val]
                else:
                    return str(il.val)
        elif il.src == optools.fs_input:
            if isinstance(il.val,list):
                return [str(v) for v in il.val]
            else:
                return str(il.val)
        else: 
            msg = 'found input source {}, should be one of {}'.format(
            il.src, optools.valid_sources)
            raise ValueError(msg)

    def add_op(self,uri,new_op):
        """Add an Operation to the tree as a new top-level TreeItem."""
        # Count top-level rows by passing parent=QModelIndex()
        ins_row = self.rowCount(QtCore.QModelIndex())
        itm = TreeItem(ins_row,0,QtCore.QModelIndex())
        itm.set_tag( uri )
        self.beginInsertRows(QtCore.QModelIndex(),ins_row,ins_row)
        self.root_items.insert(ins_row,itm)
        self.endInsertRows()
        idx = self.index(ins_row,0,QtCore.QModelIndex()) 
        self.tree_update(idx,new_op)

    def remove_op(self,rm_idx):
        """Remove an Operation from the workflow tree"""
        rm_row = rm_idx.row()
        self.beginRemoveRows(QtCore.QModelIndex(),rm_row,rm_row)
        item_removed = self.root_items.pop(rm_row)
        self.endRemoveRows()
        self.tree_dataChanged(rm_idx)
        self.update_io_deps()

    def update_op(self,uri,new_op):
        """
        Update Operation in treeitem indicated by uri.
        It is expected that new_op is a reference to the Operation stored at uri. 
        """
        itm, idx = self.get_from_uri(uri)
        self.tree_update(idx,new_op)
        self.update_io_deps()

    # TODO: fix uri_to_dict and update_uri_dict. 
    # Currently e.g. saving op.outputs.itm fails to save itm,
    # while saving op.outputs does save itm.
    def uri_to_dict(self,uri,data):
        itm,idx = self.get_from_uri(uri)
        od = OrderedDict()
        od[itm.tag()] = (data)
        p_idx = self.parent(idx)
        # if this is a top level item, return od
        if not p_idx.isValid():
            return od
        # else, package od under its parent's tag
        else:
            return self.uri_to_dict(self.build_uri(p_idx),od)

    @staticmethod
    def update_uri_dict(d,d_new):
        #print '\n-------------\nupdating \n{} \nwith \n{}'.format(d,d_new)
        for k,v in d_new.items():
            if k in d.keys():
                if isinstance(d[k],dict) and isinstance(d_new[k],dict):
                    # embedded dicts: recurse
                    d[k] = self.update_uri_dict(d[k],d_new[k])
                else:
                    # existing key refers to non-dict: replace
                    d[k] = d_new[k]
            else:
                # no entry for this key: insert
                d[k] = v
        #print 'result: \n{} \n---------'.format(d)
        return d

    def build_dict(self,x):
        """
        Overloaded build_dict to handle Operations.
        Base class method builds dicts from other data types.
        """
        if isinstance(x,Operation):
            d = OrderedDict()
            inp_dict = {}
            for nm in x.inputs.keys():
                if x.inputs[nm] is not None:
                    inp_dict[nm] = x.inputs[nm]
                else:
                    inp_dict[nm] = x.input_locator[nm]
            d[optools.inputs_tag] = inp_dict 
            d[optools.outputs_tag] = x.outputs
        else:
            d = super(Workflow,self).build_dict(x)
        return d

    # TODO: Add checking of plugins (il.src == optools.plugin_input)
    # TODO: Add checking of fs paths (il.src == optools.fs_input)
    def update_io_deps(self):
        """
        Remove any broken dependencies in the workflow.
        Should only be called after all current data have been stored in the tree. 
        """
        for r,itm in zip(range(len(self.root_items)),self.root_items):
            op = itm.data
            op_idx = self.index(r,0,QtCore.QModelIndex())
            for name,il in op.input_locator.items():
                if il:
                    if il.src == optools.wf_input and il.tp == optools.ref_type and not self.is_good_uri(il.val):
                        #vals = optools.val_list(il)
                        #for v in vals:
                        #    if not self.is_good_uri(v):
                        self.wfman.write_log('--- clearing InputLocator for {}.{}.{} ---'.format(
                        itm.tag(),optools.inputs_tag,name))
                        op.input_locator[name] = optools.InputLocator(il.src,il.tp,None)
                        self.tree_dataChanged(op_idx)

    # TODO: the following
    def check_wf(self):
        """
        Check the dependencies of the workflow.
        Ensure that all loaded operations have inputs that make sense.
        Return a status code and message for each of the Operations.
        """
        pass

    def is_running(self):
        return self._running

    def stop_wf(self):
        self._running = False

    def get_valid_wf_inputs(self,itm):
        """
        Return all of the TreeModel uris of itm and its children
        which can be used as downstream inputs in the workflow.
        """
        # valid_wf_inputs gains the operation, its input and output dicts, and their respective entries
        valid_wf_inputs = [itm.tag(),itm.tag()+'.'+optools.inputs_tag,itm.tag()+'.'+optools.outputs_tag]
        valid_wf_inputs += [itm.tag()+'.'+optools.outputs_tag+'.'+k for k in itm.data.outputs.keys()]
        valid_wf_inputs += [itm.tag()+'.'+optools.inputs_tag+'.'+k for k in itm.data.inputs.keys()]
        return valid_wf_inputs
    
    def execution_stack(self):
        """
        Build a stack (list) of lists of TreeItems,
        such that each TreeItem list contains a set of Operations
        whose dependencies are satisfied by the operations above them.
        For Batch or Realtime operations, the layer should be of the form[batch_item,batch_stack],
        where batch_item.data is the batch controller Operation,
        and batch_stack is built from self.batch_op_stack().
        """
        stk = []
        valid_wf_inputs = []
        continue_flag = True
        while not optools.stack_size(stk) == len(self.root_items) and continue_flag:
            items_rdy = []
            for itm in self.root_items:
                if not optools.stack_contains(itm,stk):
                    if self.is_op_ready(itm,valid_wf_inputs):
                        items_rdy.append(itm)
            if any(items_rdy):
                # Which of these are not Batch/Realtime ops?
                non_batch_rdy = [itm for itm in items_rdy if not isinstance(itm.data,Batch) and not isinstance(itm.data,Realtime)]
                if any(non_batch_rdy):
                    items_rdy = non_batch_rdy
                    stk.append(items_rdy)
                    for itm in items_rdy:
                        valid_wf_inputs += self.get_valid_wf_inputs(itm)
                else:
                    b_rt_itm = items_rdy[0]
                    items_rdy = [b_rt_itm]
                    b_rt_stk,b_rt_rdy = self.batch_op_stack(b_rt_itm,valid_wf_inputs)
                    stk.append([b_rt_itm,b_rt_stk])
                    valid_wf_inputs += self.get_valid_wf_inputs(b_rt_itm)
            else:
                continue_flag = False
        #print 'RESOLVED A STACK'
        #print 'STACK PRINTOUT:'
        #print optools.print_stack(stk)
        return stk

    def is_op_ready(self,itm,valid_wf_inputs,batch_routes=[]):
        if isinstance(itm.data,Batch):
            b_stk,op_rdy = self.batch_op_stack(itm,valid_wf_inputs)
        elif isinstance(itm.data,Realtime):
            rt_stk,op_rdy = self.batch_op_stack(itm,valid_wf_inputs)
        else:
            op = itm.data
            inputs_rdy = []
            for name,il in op.input_locator.items():
                # TODO: Come up with a more airtight set of conditions here.
                # Should check for valid plugin inputs.
                # Possibly also check fs inputs.
                if il.src == optools.wf_input and il.tp == optools.ref_type and not il.val in valid_wf_inputs:
                    inp_rdy = False
                elif il.src == optools.batch_input and not itm.tag()+'.'+optools.inputs_tag+'.'+name in batch_routes:
                    inp_rdy = False
                else:
                    inp_rdy = True
                inputs_rdy.append(inp_rdy)
            if all(inputs_rdy):
                op_rdy = True
            else:
                op_rdy = False
        return op_rdy 

    def batch_op_stack(self,b_itm,valid_wf_inputs):
        """
        Use b_itm.data.batch_ops() and a list of valid_wf_inputs 
        (a list of uris that are good inputs from the workflow)   
        to build a stack (list) of lists of operations 
        such that all Operations in the stack have their dependencies satisfied
        by the Operations above them.     
        """
        if isinstance(b_itm.data,Realtime):
            exec_itms = [self.get_from_uri(uri)[0] for uri in b_itm.data.realtime_ops()]
        elif isinstance(b_itm.data,Batch):
            exec_itms = [self.get_from_uri(uri)[0] for uri in b_itm.data.batch_ops()]
        else:
            exec_itms = []
        # make a copy of valid_wf_inputs and add the batch's own i/o items to the list
        valid_batch_inputs = copy.copy(valid_wf_inputs)+self.get_valid_wf_inputs(b_itm)
        layer = []
        for test_itm in exec_itms:
            if self.is_op_ready(test_itm,valid_batch_inputs,b_itm.data.input_routes()):
                layer.append(test_itm)
        b_stk = []
        while any(layer):
            b_stk.append(layer)
            for itm in layer:
                valid_batch_inputs += self.get_valid_wf_inputs(itm)
            layer = []
            for test_itm in exec_itms:
                if self.is_op_ready(test_itm,valid_batch_inputs,b_itm.data.input_routes()) and not optools.stack_contains(test_itm,b_stk):
                    layer.append(test_itm)
        b_rdy = len(exec_itms) == optools.stack_size(b_stk) 
        return b_stk,b_rdy 

    def run_wf(self):
        self._running = True
        stk = self.execution_stack()
        msg = 'STARTING EXECUTION\n----\nexecution stack: \n'
        msg += optools.print_stack(stk)
        msg += '\n----'
        self.wfman.write_log(msg)
        batch_flags = [isinstance(itm_lst[0].data,Batch) for itm_lst in stk]
        rt_flags = [isinstance(itm_lst[0].data,Realtime) for itm_lst in stk]
        layers_done = 0
        while not layers_done == len(stk): 
            # check if we are at a batch or rt op
            if batch_flags[layers_done]:
                self.run_wf_batch(stk[layers_done][0],stk[layers_done][1])
                layers_done += 1
            elif rt_flags[layers_done]:
                self.run_wf_realtime(stk[layers_done][0],stk[layers_done][1])
                layers_done += 1
            else:
                # get the portion of the stack from here to the next batch or rt op
                if (True in batch_flags[layers_done:]):
                    substk = stk[layers_done:layers_done+batch_flags[layers_done:].index(True)]
                elif (True in rt_flags[layers_done:]):
                    substk = stk[layers_done:layers_done+rt_flags[layers_done:].index(True)]
                else:
                    substk = stk[layers_done:]
                self.run_wf_serial(substk)
                layers_done += len(substk)
        # if not yet interrupted, wait for all threads to finish, then signal done
        if self.is_running():
            self.wfman.wait_for_threads()
            self.wfman.write_log('EXECUTION FINISHED')
            self.exec_finished.emit()

    def run_wf_serial(self,stk,thd_idx=None):
        """
        Serially execute the operations contained in the stack stk.
        """
        if not thd_idx:
            thd_idx = self.wfman.next_available_thread()
        for lst in stk:
            self.wfman.wait_for_thread(thd_idx)
            for itm in lst: 
                op = itm.data
                self.load_inputs(op)
            lst_copy = copy.deepcopy(lst)
            # Make a new Worker, give None parent so that it can be thread-mobile
            wf_wkr = WfWorker(lst_copy,None)
            wf_wkr.opDone.connect(self.updateOperation)
            wf_thread = QtCore.QThread(self)
            wf_wkr.moveToThread(wf_thread)
            wf_thread.started.connect(wf_wkr.work)
            wf_thread.finished.connect( partial(self.wfman.finish_thread,thd_idx) )
            self.wfman.register_thread(thd_idx,wf_thread)
            wf_thread.start()
            msg = 'running {} in thread {}'.format([itm.tag() for itm in lst_copy],thd_idx)
            self.wfman.write_log(msg)
            # TODO: Figure out how to remove this wait_for_thread() without freezing execution.
            # This is the next step towards multi-threaded batch execution.
            self.wfman.wait_for_thread(thd_idx)

    def run_wf_realtime(self,rt_itm,stk):
        """
        Executes the workflow under the control of one Realtime controller Operation,
        where the realtime controller Operation is found at rt_itm.data.
        """
        rt = rt_itm.data
        self.load_inputs(rt)
        rt.run()
        self.update_op(rt_itm.tag(),rt)
        nx = 0
        while self._running:
            # TODO: Ensure rt execution runs smoothly on an initially empty input_iter().
            # TODO: Add a way to stop a realtime execution without stopping the whole workflow.
            # After rt.run(), it is expected that rt.input_iter()
            # will generate lists of input values whose respective routes are rt.input_routes().
            # unless there are no new inputs to run, in which case it will iterate None. 
            vals = rt.input_iter().next()
            if not None in vals:
                inp_dict = dict( zip(rt.input_routes(), vals) )
                #if inp_dict and not None in vals:
                waiting_flag = False
                nx += 1
                for uri,val in inp_dict.items():
                    self.set_op_input_at_uri(uri,val)
                #thd = self.next_available_thread()
                thd = 0
                self.wfman.write_log( 'REALTIME EXECUTION {} in thread {}'.format(nx,thd))
                self.run_wf_serial(stk,thd)
                opdict = OrderedDict()
                for uri in rt.saved_items():
                    itm,idx = self.get_from_uri(uri)
                    itm_dict = self.uri_to_dict(uri,copy.deepcopy(itm.data))
                    opdict = self.update_uri_dict(opdict,itm_dict)
                rt.output_list().append(opdict)
                # TODO: not a full op update here- just update the new/changed children of the rt op
                self.update_op(rt_itm.tag(),rt)
            else:
                if not waiting_flag:
                    self.wfman.write_log( 'Waiting for new inputs...' )
                waiting_flag = True
                self.wfman.loopwait(rt.delay())
        self.wfman.write_log( 'REALTIME EXECUTION TERMINATED' )
        return

    def run_wf_batch(self,b_itm,stk):
        """
        Executes the items in the stack stk under the control of one Batch controller Operation
        """
        b = b_itm.data
        self.load_inputs(b)
        b.run()
        self.update_op(b_itm.tag(),b)
        # After b.run(), it is expected that b.input_list() will refer to a list of dicts,
        # where each dict has the form [workflow tree uri:input value]. 
        for i in range(len(b.input_list())):
            if self._running:
                input_dict = b.input_list()[i]
                for uri,val in input_dict.items():
                    self.set_op_input_at_uri(uri,val)
                # inputs are set, run in serial 
                thd = self.wfman.next_available_thread()
                #thd = 0
                #self.wfman.wait_for_thread(thd)
                self.wfman.write_log( 'BATCH EXECUTION {} / {} in thread {}'.format(i+1,len(b.input_list()),thd) )
                self.run_wf_serial(stk,thd)
                opdict = OrderedDict()
                for uri in b.saved_items():
                    itm,idx = self.get_from_uri(uri)
                    itm_dict = self.uri_to_dict(uri,copy.deepcopy(itm.data))
                    opdict = self.update_uri_dict(opdict,itm_dict)
                b.output_list()[i] = opdict
                self.update_op(b_itm.tag(),b)
            else:
                self.wfman.write_log( 'BATCH EXECUTION TERMINATED' )
                return
        self.wfman.write_log( 'BATCH EXECUTION FINISHED' )

    def set_op_input_at_uri(self,uri,val):
        """
        Set an op input, indicated by uri, to provided value.
        uri must be of the form op_name.inputs.input_name.
        Currently shallower uris (e.g. op_name.inputs) 
        and deeper uris (e.g. op_name.inputs.input_list.0)
        are not supported.
        """
        p = uri.split('.')
        op_itm, idx = self.get_from_uri(p[0])
        op = op_itm.data
        op.inputs[p[2]] = val
        op.input_locator[p[2]].data = val

    #def data(self,itm_idx,data_role):
    #    currently using super().data() 

    # Overloaded headerData() for Workflow 
    def headerData(self,section,orientation,data_role):
        if (data_role == QtCore.Qt.DisplayRole and section == 0):
            return "Current workflow: {} operation(s)".format(self.rowCount(QtCore.QModelIndex()))
        elif (data_role == QtCore.Qt.DisplayRole and section == 1):
            #return "type"
            return super(Workflow,self).headerData(section,orientation,data_role)    
        else:
            return None

    # Overload columnCount()
    #def columnCount(self,parent):
    #    return 2






