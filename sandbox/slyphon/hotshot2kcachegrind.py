#!/usr/bin/env python
# _*_ coding: latin1 _*_
#
# Copyright (c) 2003 by WEB.DE, Karlsruhe
# Autor: Jörg Beyer <job@webde-ag.de>
#
# hotshot2cachegrind is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#
#
# This script transforms the pstat output of the hotshot
# python profiler into the input of kcachegrind. 
#
# example usage:
# modify you python script to run this code:
#
# import hotshot
# filename = "pythongrind.prof"
# prof = hotshot.Profile(filename, lineevents=1)
# prof.runcall(run) # assuming that "run" should be called.
# prof.close()
#
# it will run the "run"-method under profiling and write
# the results in a file, called "pythongrind.prof".
#
# then call this script:
# hotshot2cachegrind -o <output> <input>
# or here:
# hotshot2cachegrind cachegrind.out.0 pythongrind.prof
#
# then call kcachegrind:
# kcachegrind cachegrind.out.0
#
# snatched from the web at: http://mail.python.org/pipermail/python-list/2003-September/183887.html
#
import os, sys
from hotshot import stats,log
import os.path 


what2text = { 
    log.WHAT_ADD_INFO    : "ADD_INFO", 
    log.WHAT_DEFINE_FUNC : "DEFINE_FUNC", 
    log.WHAT_DEFINE_FILE : "DEFINE_FILE", 
    log.WHAT_LINENO      : "LINENO", 
    log.WHAT_EXIT        : "EXIT", 
    log.WHAT_ENTER       : "ENTER"}

# a pseudo caller on the caller stack. This represents
# the Python interpreter that executes the given python 
# code.
root_caller = ("PythonInterpreter",0,"execute")

class Stack:
    """A tiny Stack implementation, based on python lists"""
    def __init__(self):
       self.stack = []
    def push(self, elem):
        """put something on the stack"""
        self.stack = [elem] + self.stack

    def pop(self):
        """get the head element of the stack and remove it from teh stack"""
        head = self.stack[0]
        self.stack = self.stack[1:]
        return head

    def top(self):
        """get the head element of the stack, stack is unchanged."""
        head = self.stack[0]
        return head
    def size(self):
        """ return how many elements the stack has"""
        return len(self.stack)

def do_calls(output, current_function, current_source_file, costs):
    """print, what kcachegrind needs for a function call"""
    output.write("cfn=%s\n" % current_function)
    output.write("calls=1\n0 %d\n" % costs)
    output.write("fn=%s\n" % current_function)

def return_from_call(caller_stack, call_dict, current_cost):
    """return from a function call
       remove the function from the caller stack,
       add the costs to the calling function.
    """
    called, cost_of_left_funct = caller_stack.pop()
    caller, caller_cost = caller_stack.pop()
    #print "pop: caller: %s size: %d" % (caller, caller_stack.size())

    per_file_dict = call_dict.get(caller[0], {})
    per_caller_dict = per_file_dict.get(caller[2], {})
    call_cost, count = per_caller_dict.get(called, (0, 0))
    cost_of_left_funct += current_cost


    per_caller_dict[called] = (call_cost+cost_of_left_funct, count + 1)
    per_file_dict[caller[2]] = per_caller_dict
    call_dict[caller[0]] = per_file_dict
    #print "push caller %s, size: %d : %s" % (caller, caller_stack.size(), (caller,caller_cost + cost_of_left_funct))
    caller_stack.push((caller,caller_cost + cost_of_left_funct))

def convertProfFiles(output, inputfilenames):
    """convert all the given input files into one kcachegrind 
       input file.
    """
    call_dict = {}
    cost_per_line = {}
    cost_per_function = {}
    caller_stack = Stack()
    caller_stack.push((root_caller, 0))

    total_cost = 0
    i = 0
    number_of_files = len(inputfilenames)
    for inputfilename in inputfilenames:
        i += 1
        sys.stdout.write("lese File %d von %d, costs: %s    \r" % (i, number_of_files, total_cost))
        sys.stdout.flush()
        cost = convertProfFile(inputfilename, caller_stack, call_dict, cost_per_line, cost_per_function)
        total_cost += cost
    
    print
    print "total_cost:",total_cost
    dumpResults(output, call_dict, total_cost, cost_per_line, cost_per_function)

def convertProfFile(inputfilename, caller_stack, call_dict, cost_per_line, cost_per_function):
    """convert a single input file into one kcachegrind
       data.
    """

    item_counter = 0
    total_cost = 0
    try:
        logreader = log.LogReader(inputfilename)
        current_cost = 0
        last_file = None
        last_func = None
        for item in logreader:
            item_counter += 1
            what, pos ,tdelta = item
            (file, lineno, func)  = pos
            #line = "%s %s %d %s %d" % (what2text[what], file, lineno, func, tdelta)
            #print line
            #if what == log.WHAT_LINENO:
            if what == log.WHAT_ENTER:
                caller_stack.push((pos, tdelta))
            elif what == log.WHAT_EXIT:
                return_from_call(caller_stack, call_dict, tdelta)
            else:
                # add the current cost to the current function
                p, c = caller_stack.pop()
                c += tdelta
                caller_stack.push((p,c))

            cost = cost_per_line.get(pos, 0)
            #print "buche tdelta: %d auf pos: %s -> %d" % (tdelta, pos, cost + tdelta)
            cost_per_line[pos] = cost + tdelta
            total_cost += tdelta

        # I have no idea, why sometimes the stack is not empty - we
        # have to rewind the stack to get 100% for the root_caller
        while caller_stack.size() > 1:
            return_from_call(caller_stack, call_dict, 0)

    except IOError:
        print "could not open inputfile '%s', ignore this." % inputfilename
    except EOFError, m:
        print "item_counter: %d %s" % (item_counter, m)
    return total_cost

def pretty_name(file, function):
    #pfile = os.path.splitext(os.path.basename(file)) [0]
    return "%s [%s]" % (function, file)
    #return "%s_%s" % (pfile, function)

def write_fn(output, file, function):
    output.write("fn=%s\n" % pretty_name(file, function))

def write_fl(output, file, function):
    output.write("fl=%s\n" % pretty_name(file, function))

def write_cfn(output, file, function):
    output.write("cfn=%s\n" % pretty_name(file, function))

def dumpResults(output, call_dict, total_cost, cost_per_line, cost_per_function):
    """write the collected results in the format kcachegrind
       could read.
    """
    # the intro
    output.write("events: Tick\n")
    output.write("summary: %d\n" % total_cost)
    output.write("cmd: your python script\n")
    output.write("\n")
    last_func = None
    last_file = None
    # now the costs per line
    for pos in cost_per_line.keys():
        output.write("ob=%s\n" % pos[0])
        write_fn(output, pos[0], pos[2])
        # cost line
        output.write("%d %d\n" % (pos[1], cost_per_line[pos]))
    output.write("\n\n")
    # now the function calls. For each caller all the called
    # functions and their costs are written.
    for file in call_dict.keys():
        per_file_dict = call_dict[file]
        output.write("ob=%s\n" % file)
        #print "file %s -> %s" % (file, per_file_dict)
        for caller in per_file_dict.keys():
            write_fn(output, file ,caller)
            write_fl(output, file ,caller)
            per_caller_dict = per_file_dict[caller]
            #print "caller %s -> %s" % (caller, per_caller_dict)
            for called in per_caller_dict.keys():
                output.write("cob=%s\n\ncfl=%s\n" % (called[0], called[0]))
                write_cfn(output, called[0], called[2])
                cost, count = per_caller_dict[called]
                # detect recursion
                if file == called[0] and caller == called[2]:
                    output.write("r");
                output.write("calls=%d\n%d %d\n" % (count, called[1], cost))
                #output.write("calls=%d\n%d %d\n" % (count, called[1], cost))

def run_without_optik():
    """parse the options without optik, use sys.argv"""
    if  len(sys.argv) < 4 or sys.argv[1] != "-o" :
        print "usage: hotshot2cachegrind -o outputfile in1 [in2 [in3 [...]]]"
        return
    outputfilename = sys.argv[2]
    try:
        output = file(outputfilename, "w")
        args = sys.argv[3:]
        convertProfFiles(output, args)
        output.close()
    except IOError:
        print "could not open '%s' for writing." % outputfilename

def run_with_optik():
    """parse the options with optik"""
    parser = OptionParser()
    parser.add_option("-o", "--output",
      action="store", type="string", dest="outputfilename",
      help="write output into FILE")
    output = sys.stdout
    close_output = 0
    (options, args) = parser.parse_args()
    try:
        if options.outputfilename and options.outputfilename != "-":
            output = file(options.outputfilename, "w")
            close_output = 1
    except IOError:
        print "could not open '%s' for writing." % options.outputfilename
    if output:
        convertProfFiles(output, args)
        if close_output:
            output.close()


# check if optik is available.
try:
    from optik import OptionParser
    run = run_with_optik
except ImportError:
    run = run_without_optik

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass


