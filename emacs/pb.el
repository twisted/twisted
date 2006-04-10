;;;; pb.el - a perspective broker implementation for emacs
;;;; by Allen Short <washort@twistedmatrix.com>
;;;; this file is in the public domain.

"'We will never run out of things to program as long as there is a
  single program around.' -- Alan Perlis, Programming Epigram #100"

(require 'banana)
(require 'jelly)
(provide 'pb)

(defconst pb-version 6)
(defconst pb-port 8787)
(defstruct pb-broker
  (perspectives ())
  socket
  (waiting-for-answers (make-hash-table))
  (request-id 0)
  (disconnected nil)
  requested-identity
  (local-objects (make-hash-table)))

(defsubst hexchar-to-int (hex)
  (cond
   ((and (<= ?0 hex) (<= hex ?9)) (- hex ?0))
   ((and (<= ?A hex) (<= hex ?F)) (+ (- hex ?A) 10))
   ((and (<= ?a hex) (<= hex ?f)) (+ (- hex ?a) 10))))

(defun md5-raw (str)
  (let* ((md5str (md5 str))
	 (len (length md5str))
	 (md5raw (make-string (/ len 2) 0))
	 (i 0) (j 0))
    (while (< i len)
      (aset md5raw j (+ (* (hexchar-to-int (aref md5str i)) 16)
			(hexchar-to-int (aref md5str (1+ i)))))
      (setq i (+ i 2))
      (setq j (1+ j)))
    md5raw))

(defun pb-passport-respond (challenge password)
  (md5-raw (concat (md5-raw password) challenge)))

(defun netjelly-unserialize (broker jelly)
  (let ((refs (make-hash-table)))
    (jelly-fixup-refs (netjelly-unserialize-internal broker jelly))))



(defun netjelly-unserialize-internal (broker jelly)
  ;; some days i think glyph does these things on purpose, to annoy me
  (if (or (integerp jelly) (stringp jelly) (floatp jelly) (null jelly))
      jelly
    (ecase (intern (car jelly))
      ((list tuple)
       (mapcar (lambda (i) (netjelly-unserialize-internal broker i)) (cdr jelly)))
      (dictionary
       (let ((ht (make-hash-table)))
         (mapc
          (lambda (pair)
            (let ((k (car pair)) (v (second pair)))
              (setf (gethash k ht) (netjelly-unserialize-internal broker v))))
          (cdr jelly))
         ht))
      ((integer string float)
       (lambda () (cdr jelly)))
      (reference
       (let ((val  (netjelly-unserialize-internal broker (third jelly))))
         (setf (gethash (second jelly) refs) val)
         val))
      (dereference
       (lexical-let ((-ref-num- (cadr jelly)))
         (lambda () (gethash -ref-num- refs))))
      (remote
       (make-remote-reference nil broker (cadr jelly)))
      (local
       (gethash (cadr jelly) (pb-broker-local-objects broker))))))



(defun make-remote-reference (perspective broker luid)
  (lexical-let ((-perspective- perspective) (-broker- broker) (-luid- luid))
    (lambda (message args kwargs &optional callback errback)
      ;; remote-serialize(broker val)
      (if (equal message 'remote-serialize)
          (progn
            (unless (eq -broker- (car args))
              (error "Can't send references to brokers other than their own."))
            (list 'local -luid-))
        (pb-send-message -broker- -perspective- -luid- message args kwargs callback errback)))))

(defun pb-traceback (tb)
  (let ((b (get-buffer-create "*PB Traceback*")))
    (pop-to-buffer b)
    (print tb b)))


(defsubst pb-send-call (broker &rest args)
  (banana-send-encoded (pb-broker-socket broker) args))

(defun pb-send-message (broker perspective obj-id message args kwargs callback errback)
  (if (pb-broker-disconnected broker) (error "calling stale broker"))
  (let ((net-args (jelly-serialize args (make-jelly)))
        (net-kw (jelly-serialize-alist kwargs (make-jelly)))
        (request-id (incf (pb-broker-request-id broker)))
        (answer-required (if (or callback errback) 1 0)))
    (puthash request-id (cons callback errback) (pb-broker-waiting-for-answers broker))
    (pb-send-call broker "message" request-id obj-id message answer-required net-args net-kw)))

(defun pb-connect-internal (host port callback)
  (let ((broker (make-pb-broker))
        (sock (open-network-stream "pb" nil host (or port pb-port))))
    (setf (pb-broker-socket broker) sock)
    (set-process-filter
     sock
     (lexical-let ((-broker- broker)
                   (-callback- callback))
       (make-banana-decoder
        (lambda (expr) (pb-socket-filter -broker- expr))
        (lambda () (funcall -callback- -broker-)))))
    broker))

(defun pb-get-object-at (host port callback  &optional errback timeout)
;;   (let ((b (pb-connect-internal host port)))
;;     (funcall callback (make-remote-reference nil b "root")))
  (lexical-let ((-callback- callback))
    (pb-connect-internal
     host port 
     (lambda (b) (funcall -callback- (make-remote-reference nil b "root"))))))

(defun pb-connect (callback errback host port username password service &optional perspective client timeout)
  ;; the proper indentation of this code is left as an exercise for the reader
  (lexical-let ((-callback- callback)
                (-errback- errback)
                (-username- username)
                (-password- password)
                (-service- service)
                (-perspective- perspective)
                (-client- client))
    (pb-get-object-at
     host port
     (lambda (authserv)
       (funcall authserv "username"
                (list -username-) nil
                (lambda (chal)
                  (funcall (second chal) "respond"
                           (list (pb-passport-respond (first chal) -password-)) nil
                           (lambda (identity)
                             (if identity
                                 (funcall identity "attach"
                                          (list -service- (or -perspective- -username-) -client-) nil
                                          -callback-
                                          -errback-)
                               (funcall -errback- "invalid username or password")))
                           -errback-))
                -errback-))
     (lambda (error) (funcall -errback- error))
     timeout)))

(defun pb-socket-filter (broker sexp)
  (if (listp (car sexp))
      (mapcar (lambda (s) (pb-dispatch broker s)) sexp)
    (pb-dispatch broker sexp)))

(defun pb-dispatch (broker expr)
  (let ((fun (symbol-function 
              (intern (concat "pb-proto-" (car expr))))))
  (apply fun (cons broker (cdr expr)))))

(defun pb-proto-version (broker vnum)
  (unless (eq vnum pb-version) (error "Incompatible protocol versions")))

(defun pb-proto-answer (broker request-id net-result)
  (let ((funs (gethash request-id (pb-broker-waiting-for-answers broker))))
    (remhash request-id (pb-broker-waiting-for-answers broker))
    (funcall (car funs) (netjelly-unserialize broker net-result))))

(defun pb-shutdown (broker)
  (let ((h (pb-broker-waiting-for-answers broker)))
    (maphash (lambda (k v)
               (remhash k h)
               (funcall (cdr v) "Connection lost"))
             h))
  ;;(mapcar #'funcall (pb-broker-disconnects broker))
  (delete-process (pb-broker-socket broker))
  (setf (pb-broker-disconnected broker) t))
