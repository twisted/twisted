
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Debugging Python(Twisted) with Emacs
====================================

- Open up your project files. sometimes emacs can't find them if you
  don't have them open before-hand.
- Make sure you have a program called ``pdb`` somewhere
  in your PATH, with the following contents:
  
  
  
  .. code-block:: console
  
      #!/bin/sh
      exec python -m pdb $1 $2 $3 $4 $5 $6 $7 $8 $9
  
- Run ``M-x pdb`` in emacs. If you usually run your
  program as ``python foo.py`` , your command line should be ``pdb foo.py`` , for ``twistd`` and ``trial`` just
  add -b to the command line, e.g.: ``twistd -b -y  my.tac`` 
- While pdb waits for your input, go to a place in your code and hit
  ``C-x SPC`` to insert a break-point. pdb should say something happy.
  Do this in as many points as you wish.
- Go to your pdb buffer and hit ``c`` ; this runs as normal until a
  break-point is found.
- Once you get to a breakpoint, use ``s`` to step, ``n`` to run the
  current line without stepping through the functions it calls, ``w`` 
  to print out the current stack, ``u`` and ``d`` to go up and down a
  level in the stack, ``p foo`` to print result of expression ``foo`` .
- Recommendations for effective debugging:
  
  
  
  - use ``p self`` a lot; just knowing the class where the current code
    is isn't enough most of the time.
  - use ``w`` to get your bearings, it'll re-display the current-line/arrow
  - after you use ``w`` , use ``u`` and ``d`` and lots more ``p self`` on the
    different stack-levels.
  - If you've got a big code-path that you need to grok, keep another
    buffer open and list the code-path there (e.g., I had a
    nasty-evil Deferred recursion, and this helped me tons)
  
  
  







.. rubric:: Footnotes
