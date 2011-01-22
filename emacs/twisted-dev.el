;; Instructions for Use

;; In your ~/.emacs, write:
;;   (setq load-path (cons "path/to/Twisted/emacs" load-path))
;;   (require 'twisted-dev)
;;
;; twisted-dev-mode (minor editing mode) will be auto-loaded
;; when editing any files under you twisted-dev-directory
;;
;; This module can be customized.  Try M-x customize-group twisted-dev
;;
;; Now, you will be able to do various things at the push of a button:
;;
;;   f7: build all howtos
;;   f8: run pyflakes over the current code
;;   f9: run unit tests specific to current code
;;   S-f9: run all unit tests, no confirmation
;;   M-f9: run unit tests specific to current code under debugger
;;   f11: grep through twisted source
;;
;; If you wish to associate a unit test with a particular bit of code, and the
;; test code (as normal for Twisted modules)is in the module
;; twisted.test.test_$TEST_NAME, you can make it run automatically by making
;; the first line of the file:
;;
;;   # -*- test-case-name: "twisted.test.test_$TEST_NAME" -*-


(provide 'twisted-dev)

(setq twisted-dev-is-xemacs
      (eq nil
	  (string-match "^GNU" (version))))
(setq twisted-dev-is-gnumacs (not twisted-dev-is-xemacs))

(setq twisted-dev-isnt-windows (eq nil (string-match "mingw" (version))))
(setq twisted-dev-is-windows (not twisted-dev-isnt-windows))


(defun better-pdb (&optional command-line)
  (interactive)
  (let ((result (if command-line
		   (pdb command-line)
		 (call-interactively 'pdb command-line))))
    (gud-def gud-break  "break %d%f:%l"     "\C-b" "Set breakpoint at current line.")
    (gud-def gud-remove "clear %d%f:%l"     "\C-d" "Remove breakpoint at current line")
    result))

(defgroup twisted-dev nil
  "Various Twisted development utilities."
  :group 'development)

(defcustom twisted-dev-directory "~/Projects/Twisted"
  "*Directory to base all twisted-dev utilities out of."
  :group 'twisted-dev
  :type 'string)


(defcustom twisted-dev-tbformat "emacs"
  "*Traceback format for trial"
  :group 'twisted-dev
  :type 'string)


(defcustom twisted-dev-scratch-directory "~/Scratch/Test"
  "*Directory to base all twisted-dev scratch operations (like unit tests)
  from."
  :group 'twisted-dev
  :type 'string)

(defcustom twisted-dev-confirm-run-all nil
  "If t, confirm running of all Twisted tests."
  :group 'twisted-dev
  :type 'boolean)


(defun twisted-dev-pyflakes-thisfile ()
  (interactive)
  (compile (format "pyflakes %s" (buffer-file-name))))

(defun twisted-dev-natives-compile ()
  (interactive)
  (with-cd twisted-dev-directory
	   (compile "python setup.py build_ext")))

(defvar test-case-name nil "Hello")
(make-variable-buffer-local 'test-case-name)

(defmacro with-cd (dirname &rest code)
  `(let ((old-dirname default-directory)
	 (start-buffer (current-buffer)))
     (cd ,dirname)
     (unwind-protect (progn ,@code)
       (let ((end-buffer (current-buffer)))
	 ;; (cd ,dirname)
	 (set-buffer start-buffer)
	 (cd old-dirname)
	 (set-buffer end-buffer)))))

;; (list default-directory (with-cd "/" (list default-directory (error "hi")) default-directory))

(defun show-test-case-name ()
  (interactive)
  (message (format "%s" test-case-name)))

(defun twisted-dev-run-all-tests ()
  (interactive)
  (twisted-dev-runtests nil t))

(defun twisted-dev-confirm (confvar dispm dispy dispn)
  (message (format "%s (y/n)" dispm))
  (if (or (not confvar) (eq (read-char) 121))
      (progn
	(message dispy)
	t)
    (progn
      (message dispn)
      nil)))

;;; NOTE:

;;; twisted-dev-runtests's debug behavior will probably seem weird if you set
;;; gud-chdir-before-run to ON, which is its default.  If you seem to be going
;;; to the wrong directory, try turning this off.

(defun twisted-dev-runtests (&optional debug noprompt)
  (interactive)
  (with-cd twisted-dev-scratch-directory
	   (hack-local-variables)
	   (let* ((bfn (buffer-file-name))
		  ;; this whole pile of crap is to compensate for the fact that

		  ;;   a. debian glibc is buggy with 2.6.5+ kernels and sends
		  ;;   SIGHUP to processes run in the way that emacs
		  ;;   asynchronous process runner runs them when threads
		  ;;   terminate, which certain unit tests don't

		  ;;   b. gud randomly corrupts the commandline in such a way
		  ;;   that it is impossible to pass commandlines around - it
		  ;;   considers anything that doesn't start with a "-" to be a
		  ;;   filename, and (incorrectly, due to the fact that we're
		  ;;   running in a different directory than it expects)
		  ;;   expands it to be an absolute filename

                  ;;   c. windows doesn't have a shell we can invoke, and Trial
                  ;;   won't run by itself on Windows; we have to use Python or
                  ;;   Combinator (the current hack here is to use Combinator,
                  ;;   but that could be changed)

		  (shell-script-name
                   (format "%s/trialscript" twisted-dev-scratch-directory))
                  (full-trial-command-line
                   (format "trial --rterrors --reporter=bwverbose --tbformat=%s %s --testmodule=%s"
                           twisted-dev-tbformat
                           (if debug "--debug" "")
                           bfn))
		  (full-command-line (if twisted-dev-isnt-windows
                                         (progn
                                           (shell-command
                                            (format "mkdir -p %s; echo '%s/bin/%s' > %s"
                                                    twisted-dev-scratch-directory
                                                    twisted-dev-directory
                                                    full-trial-command-line
                                                    shell-script-name
                                                    ))
                                           (format "sh %s" shell-script-name))
                                       full-trial-command-line))
                  )
	     (if bfn
		 (funcall (if debug 'better-pdb 'compile)
			  full-command-line))
	     full-command-line)))

(defun twisted-dev-debug-tests ()
  (interactive)
  (twisted-dev-runtests t))

(defun twisted-dev-gendoc ()
  (interactive)
  (with-cd (format "%s/doc/howto" twisted-dev-directory)
    (compile (format "../../bin/lore -p %s" buffer-file-name))))

(defun twisted-dev-grep ()
  (interactive)
  (grep (format
	 "egrep  --recursive %s -n -e \"%s\" --include '*.py'"
	 twisted-dev-directory
	 (read-from-minibuffer "find in Twisted source: "))))

(define-minor-mode twisted-dev-mode
  "Toggle twisted-dev mode.
With no argument, this command toggles the mode.
Non-null prefix argument turns on the mode.
Null prefix argument turns off the mode."
 ;; The initial value.
 nil
 ;; The indicator for the mode line.
 " Twisted"
 ;; The minor mode bindings.
 '(
   ([f7] . twisted-dev-gendoc)
   ([f8] . twisted-dev-pyflakes-thisfile)
   ([f9] . twisted-dev-runtests)
   (let ((key-symbol
	  (if twisted-dev-is-gnumacs ;blargh :(
	      [S-f9]
	    '(shift f9))))
     (key-symbol . twisted-dev-run-all-tests))
   ([(meta f9)] . twisted-dev-debug-tests)
   ([f11] . twisted-dev-grep)
))

(add-hook
 'find-file-hooks
 (lambda ()
   (let ((full-twisted-path (expand-file-name twisted-dev-directory)))
     (if (> (length (buffer-file-name)) (length full-twisted-path))
	 (if (string=
	      (substring (buffer-file-name) 0 (length full-twisted-path))
	      full-twisted-path)
	     (twisted-dev-mode t)
	   )))))

(add-hook
 'python-mode-hook
 (lambda ()
   (twisted-dev-mode t)))
