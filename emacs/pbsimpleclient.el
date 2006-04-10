(require 'pb)
(defvar pbsimple-buf (get-buffer-create "*pbsimpleclient*"))

(defun got-object (object)
  (print "got object" pbsimple-buf)
  (funcall object "echo" '("hello network") nil #'got-echo))))

(defun got-echo (echo)
  (print (format "server echoed: %s" echo) pbsimple-buf)
  (pb-shutdown broker))
(defun got-no-object (reason)
  (print (format "no object: %s" reason) pbsimple-buf)
  (pb-shutdown broker))

(pb-get-object-at "localhost" 8789 #'got-object #'got-no-object 30)

  
