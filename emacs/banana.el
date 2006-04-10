;;;; Banana -- allows network abstraction, nearly always.
;;;; by Allen Short <washort@twistedmatrix.com>
;;;; This file is in the public domain.

"'Get into a rut early: Do the same processes the same way. Accumulate
  idioms. Standardize. The only difference(!) between Shakespeare and you was
  the size of his idiom list -- not the size of his vocabulary.'
    -- Alan Perlis, Programming Epigram #10"

(provide 'banana)
(require 'cl)

;; (defconst default-vocabulary  
;;   ;; Jelly Data Types
;;   '((None .-1)
;;     (class . -2)
;;     (dereference . -3)
;;     (reference . -4)
;;     (dictionary . -5)
;;     (function . -6)
;;     (instance . -7)
;;     (list . -8)
;;     (module . -9)
;;     (persistent . -10)
;;     (tuple . -11)
;;     (unpersistable . -12)
;;     ;; PB Data Types
;;     (copy . -13)
;;     (cache . -14)
;;     (cached . -15)
;;     (remote . -16)
;;     (local . -17)
;;     (lcache . -18)
;;     ;; PB Protocol Messages
;;     (version . -19)
;;     (login . -20)
;;     (password . -21)
;;     (challenge . -22)
;;     (logged-in . -23)
;;     (not-logged-in . -24)
;;     (cachemessage . -25)
;;     (message . -26)
;;     (answer . -27)
;;     (error . -28)
;;     (decref . -29)
;;     (decache . -30)
;;     (uncache . -31)))

(defun banana-int-char (c)
  c)

(defconst high-bit (banana-int-char 128))
(defconst list-type (banana-int-char 128))
(defconst int-type (banana-int-char 129))
(defconst string-type (banana-int-char 130))
(defconst neg-type (banana-int-char 131))
(defconst float-type (banana-int-char 132))

(defmacro special-case (expr &rest clauses)
  (append (list 'ecase expr)
          (mapcar
           (lambda (i)
             (cons (eval (car i)) (cdr i))) clauses)))

(defun read-integer-base128 (string)
  (loop for i = 0 then (+ i (* (char-int char) (expt 128 place)))
        for place = 0 then (1+ place)
        for char across string
        finally return i))

(defun make-banana-decoder (data-received connection-ready)
  (lexical-let ((-stack- ())
                (-buffer- "")
                (-output- ())
                (-data-received- data-received)
                (-connection-ready- connection-ready)
                (-vocab- nil))
    (lambda (socket chunk)
      (block nil
        (flet ((eat-item (item)
                 (if -stack-
                     (setf (cdar -stack-) (nconc (cdar -stack-) (list item)))
                   (setf -output-  item))))
        (let ((buffer (concat -buffer- chunk)))
          (while (/= (length buffer) 0)
            (let* ((pos (let ((i 0)) (loop ;junk
                                       for ch across buffer
                                       while (< ch high-bit)
                                       do (incf i)) i))
                   (num-string (substring buffer 0 pos))
                   (num (read-integer-base128 num-string))
                   (type-byte (aref buffer pos))
                   (rest (substring buffer (1+ pos))))
              (setq -buffer- buffer)
              (special-case type-byte
                (list-type 
                 (setq -stack- (acons num '() -stack-))
                 (setq buffer rest))
                (string-type 
                 (if (>= (length rest) num) 
                     (progn
                       (setq buffer (substring rest num))
                       (eat-item (substring rest 0 num)))
                   (return)))
                (int-type 
                 (setf buffer rest)
                 (eat-item num))
                (neg-type 
                 (setf buffer rest)
                 (eat-item (- num)))
                (float-type 
                 (setf buffer rest)
                 (string-to-number num-string)))
              (loop while (and -stack- 
                               (= (length (cdar -stack-))
                                  (caar -stack-)))
                do (eat-item (cdr (pop -stack-))))))
          (setf -buffer- ""))))
      (when (null -stack-) 
        ;; (print -output- (get-buffer-create "*banana-debug*"))
        (if -vocab-
            (progn
              (funcall -data-received- -output-) (setf -output- nil))
          (progn
            (setf -vocab- "none")
            (banana-send-encoded socket "none")
            (funcall -connection-ready-)))))))

(defun print-integer-base128 (int stream)
  (if (= int 0) 
      (print (banana-int-char 0) stream)
    (if (< int 0) 
        (error "positive numbers only. blame Allen for breaking it")
      (loop 
        until (<= int 0)
        do (write-char (banana-int-char (logand int 127)) stream)
           (setf int (ash int -7))))))
        


(defun banana-encode (obj stream)
  (cond
   ((listp obj)
    (print-integer-base128 (length obj) stream)
    (write-char list-type stream)
    (mapc (lambda (x) (banana-encode x stream)) obj))
   ((integerp obj)
    (print-integer-base128 (abs obj) stream)
    (if (>= obj 0)
        (write-char int-type stream)
      (write-char neg-type stream)))
   ((floatp obj)
    (prin1 obj stream)
    (write-char float-type))
   ((stringp obj)
    (print-integer-base128 (length obj) stream)
    (write-char string-type stream)
    (princ obj stream))
   ((symbolp obj)
    ;; (let ((code (cdr (assoc obj default-vocabulary))))
    ;;       (if (null code) 
    ;;           (error "Unrecognised jelly symbol"))
    ;;       (when (< code 0)
    ;;           (print-integer-base128 (- code) stream)
    ;;           (write-char vocab-type stream)))
    (let ((my-symbol-name (symbol-name obj)))
      (print-integer-base128 (length my-symbol-name) stream)
      (write-char string-type stream)
      (princ my-symbol-name stream)))
   (t (error "Couldn't send object"))))
    
(defun banana-send-encoded (bse-process obj)
    (banana-encode obj (lambda (data) (process-send-string bse-process (if (stringp data) data (string data))))))
