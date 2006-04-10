;;this is all based on ielm.el -- i was planning to copy
;;inferior-emacs-lisp-mode as verbatim as possible and just swap
;;function names round, and bringing in the python 
;;syntax table. obviously we send commands to the manhole server
;;instead of locally evaling,  so you can ignore all the ! ! !!! 
;;silliness. we probably want to only support one instance of this running
;;at once, so use globals to your heart's content ;)

(require 'pb)
(defvar manhole-prompt "manhole> ")
(defun manhole (host port)
  (interactive "sManhole connection to: i")
  )
(defvar manhole-input)

(defun manhole-input-sender (proc input)
  (setq manhole-input input))

(defun manhole-send-input ()
  (interactive)
  (let ((buf (current-buffer))
        manhole-input)
    (comint-send-input)
    (funcall manhole-server "do" (list manhole-input) nil #'manhole-output)))

(defun manhole-output (output)
; mung output pairs here....
  (comint-output-filter manhole-process ) ; 
  (princ manhole-prompt manhole-buffer))
