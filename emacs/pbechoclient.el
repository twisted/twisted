(require 'pb)

(defvar pbecho-buf (get-buffer-create "*pbechoclient*"))

(defun success (echo)
  (print (format "Message received: %s" echo) pbecho-buf)
  ;; (pb-shutdown broker) surprise!!
  )
(defun failure (error)
  (print (format "failure: %s" reason) pbecho-buf)
  (pb-shutdown broker))
(defun connected (perspective)
  (funcall perspective "echo" '("hello world") nil #'success #'failure)
  (print "connected." pbecho-buf))

(pb-connect #'connected #'failure "localhost" pb-port "guest" "guest" "pbecho" "guest" nil 30)

(delete-process "pb")
