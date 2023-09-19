import random

from pm4py.objects.log.obj import EventLog, Trace, Event
from pm4py.util import xes_constants as xes
from pm4py.objects.process_tree.obj import Operator
from pm4py.objects.process_tree import state as pt_st
from pm4py.objects.process_tree.utils import generic as pt_util
from pm4py.objects.process_tree.obj import ProcessTree

import datetime
from copy import deepcopy


class GenerationTree(ProcessTree):
    # extend the parent class to replace the __eq__ and __hash__ method
    def __init__(self, tree):
        i = 0
        while i < len(tree.children):
            tree.children[i] = GenerationTree(tree.children[i])
            tree.children[i].parent = self
            i = i + 1
        ProcessTree.__init__(self, operator=tree.operator, parent=tree.parent, children=tree.children, label=tree.label)

    def __eq__(self, other):
        # method that is different from default one (different taus must give different ID in log generation!!!!)
        return id(self) == id(other)

    def __hash__(self):
        return id(self)


def generate_log(pt0,actdict, no_traces=100):
    """
    Generate a log out of a process tree

    Parameters
    ------------
    pt
        Process tree
    no_traces
        Number of traces contained in the process tree

    Returns
    ------------
    log
        Trace log object
    """
    pt = deepcopy(pt0)
    #for ele in pt:
        #print(ele,'here is line 50')
    # different taus must give different ID in log generation!!!!
    # so we cannot use the default process tree class
    # we use this different one!
    pt = GenerationTree(pt)
    log = EventLog()
    #print(pt,'line 56')
    # assigns to each event an increased timestamp from 1970
    curr_timestamp = 10000000

    for i in range(no_traces):
        ex_seq = execute(pt,actdict)
        #print(ex_seq,'ex_seq')
        ex_seq_labels = pt_util.project_execution_sequence_to_labels(ex_seq)
        #print(ex_seq_labels,'ex_seq_labels')
        trace = Trace()
        trace.attributes[xes.DEFAULT_NAME_KEY] = str(i)
        #print('line 67')
        for label in ex_seq_labels:
            event = Event()
            event[xes.DEFAULT_NAME_KEY] = label
            event[xes.DEFAULT_TIMESTAMP_KEY] = datetime.datetime.fromtimestamp(curr_timestamp)

            trace.append(event)
            #print(event,'line 73')
            curr_timestamp = curr_timestamp + 1

        log.append(trace)

    return log


def execute(pt,actdict):
    """
    Execute the process tree, returning an execution sequence

    Parameters
    -----------
    pt
        Process tree

    Returns
    -----------
    exec_sequence
        Execution sequence on the process tree
    """
    enabled, open, closed = set(), set(), set()
    enabled.add(pt)
    #print(enabled,'hi enabled')
    #populate_closed(pt.children, closed)
    execution_sequence = list()
    while len(enabled) > 0:
        execute_enabled(enabled, open, closed ,actdict, execution_sequence)
    #print(execution_sequence,'line99')
    return execution_sequence


def populate_closed(nodes, closed):
    """
    Populate all closed nodes of a process tree

    Parameters
    ------------
    nodes
        Considered nodes of the process tree
    closed
        Closed nodes
    """
    closed |= set(nodes)
    for node in nodes:
        populate_closed(node.children, closed)


def execute_enabled(enabled,open,closed,actdict,execution_sequence=None):
    """
    Execute an enabled node of the process tree

    Parameters
    -----------
    enabled
        Enabled nodes
    open
        Open nodes
    closed
        Closed nodes
    execution_sequence
        Execution sequence

    Returns
    -----------
    execution_sequence
        Execution sequence
    """
    execution_sequence = list() if execution_sequence is None else execution_sequence
    vertex = random.sample(enabled, 1)[0]
    enabled.remove(vertex)
    open.add(vertex)
    #print(vertex,'vertex')
    execution_sequence.append((vertex, pt_st.State.OPEN))
    if len(vertex.children) > 0:
        #print(vertex.children,'vertex.children')
        if vertex.operator is Operator.LOOP:
            while len(vertex.children) < 3:
                vertex.children.append(ProcessTree(parent=vertex))
        if vertex.operator is Operator.SEQUENCE or vertex.operator is Operator.LOOP:
            c = vertex.children[0]
            enabled.add(c)
            execution_sequence.append((c, pt_st.State.ENABLED))
        elif vertex.operator is Operator.PARALLEL:
            enabled |= set(vertex.children)
            #print(set(vertex.children),'set(vertex.children)')
            for x in vertex.children:
                if x in closed:
                    closed.remove(x)
            map(lambda c: execution_sequence.append((c, pt_st.State.ENABLED)), vertex.children)
        elif vertex.operator is Operator.XOR:
            #print(vertex.parent,'vertex.parent')
            #print(vertex.operator,'vertex.operator')
            #pre = execution_sequence[-1]
            vc = vertex.children
            #print(vc,'vc')

            vcl = [ele.label for ele in vc]
            #print('line164',[ele.label for ele in vc])
            #compute the number of none, and then probability.
            nonec = 0
            probdominator = 0
            allnone = 1
            allnotnone = 1
            for ele in vcl:
                
                if  ele == None:
                    nonec += 1
                    allnotnone = 0
                else:
                    probdominator += actdict[ele]
                    allnone = 0
            if allnone == 1:
                nonec = nonec/2
            if allnotnone == 1:
                factor = 1
            else:
                factor = 0.5
            vclprob = []
            for ele in vcl:
                if ele == None and vclprob == []:
                    #vclprob.append(1/(nonec+1))

                    vclprob.append(1/(2*nonec))

                    #vclprob.append(0.1)

                elif ele == None and vclprob != []:

                    vclprob.append(vclprob[-1]+1/(2*nonec))

                    #vclprob.append(0.1)

                else:
                    for key in actdict:
                        if key == ele and vclprob == []:
                            vclprob.append(factor*actdict[key]/probdominator)
                            break
                        elif key == ele and vclprob != []:
                            vclprob.append(vclprob[-1]+factor*actdict[key]/probdominator)
                            break
            #print(vcl,vclprob)
            r = random.random()
            for i,ele in enumerate(vclprob):
                if r <= ele:
                    index = i
                    break
            c = vc[index]


            #c = vc[random.randint(0,len(vc)-1)]
            #print(c,'c')
            enabled.add(c)
            #print(execution_sequence[-1],execution_sequence[-1][0].label,'execution_sequence[-1]')
            execution_sequence.append((c, pt_st.State.ENABLED))
            #print(execution_sequence,'execution_sequence in XOR')
        elif vertex.operator is Operator.OR:

            vcl = [ele.label for ele in vertex.children]
            vclprob = []
            for ele in vcl:
                if ele == None:
                    vclprob.append(0.5)
                else:
                    for key in actdict:
                        if ele == key:
                            vclprob.append(actdict[key])
                            #vclprob.append(0.5)
            some_children = []
            for i,c in enumerate(vertex.children):
                if random.random() <= vclprob[i]:
                    some_children.append(c)


            #some_children = [c for c in vertex.children if random.random() < 0.5]
            enabled |= set(some_children)
            for x in some_children:
                if x in closed:
                    closed.remove(x)
            map(lambda c: execution_sequence.append((c, pt_st.State.ENABLED)), some_children)
            #print(execution_sequence,'execution_sequence in OR')
    else:
        close(vertex, enabled, open, closed, execution_sequence)
    #print(execution_sequence,'line169')
    return execution_sequence


def close(vertex, enabled, open, closed, execution_sequence):
    """
    Close a given vertex of the process tree

    Parameters
    ------------
    vertex
        Vertex to be closed
    enabled
        Set of enabled nodes
    open
        Set of open nodes
    closed
        Set of closed nodes
    execution_sequence
        Execution sequence on the process tree
    """
    open.remove(vertex)
    closed.add(vertex)
    execution_sequence.append((vertex, pt_st.State.CLOSED))
    process_closed(vertex, enabled, open, closed, execution_sequence)


def process_closed(closed_node, enabled, open, closed, execution_sequence):
    """
    Process a closed node, deciding further operations

    Parameters
    -------------
    closed_node
        Node that shall be closed
    enabled
        Set of enabled nodes
    open
        Set of open nodes
    closed
        Set of closed nodes
    execution_sequence
        Execution sequence on the process tree
    """
    vertex = closed_node.parent
    if vertex is not None and vertex in open:
        if should_close(vertex, closed, closed_node):
            close(vertex, enabled, open, closed, execution_sequence)
        else:
            enable = None
            if vertex.operator is Operator.SEQUENCE:
                enable = vertex.children[vertex.children.index(closed_node) + 1]
            elif vertex.operator is Operator.LOOP:
                enable = vertex.children[random.randint(1, 2)] if vertex.children.index(closed_node) == 0 else \
                    vertex.children[0]
            if enable is not None:
                enabled.add(enable)
                execution_sequence.append((enable, pt_st.State.ENABLED))


def should_close(vertex, closed, child):
    """
    Decides if a parent vertex shall be closed based on
    the processed child

    Parameters
    ------------
    vertex
        Vertex of the process tree
    closed
        Set of closed nodes
    child
        Processed child

    Returns
    ------------
    boolean
        Boolean value (the vertex shall be closed)
    """
    if vertex.children is None:
        return True
    elif vertex.operator is Operator.LOOP or vertex.operator is Operator.SEQUENCE:
        return vertex.children.index(child) == len(vertex.children) - 1
    elif vertex.operator is Operator.XOR:
        return True
    else:
        return set(vertex.children) <= closed
