;;;; Jelly -- portable serialisation for network communication.
;;;; by Allen Short <washort@twistedmatrix.com>
;;;; This file is in the public domain.

"'Get into a rut early: Do the same processes the same way. Accumulate idioms. Standardize. The only difference(!) between Shakespeare and you was the size of his idiom list -- not the size of his vocabulary.' -- Alan Perlis,  Programming Epigram #10"

(provide 'jelly)

(defvar jelly-debug 0)
(defstruct (jelly)
  (preserved (make-hash-table))
  (cooked (make-hash-table))
  (ref-id 0))

(defun jelly-cook (obj j)
(if jelly-debug (print (list "cook" obj j) (get-buffer "*jelly-trace*")))
  (let* ((sexp (gethash obj (jelly-preserved j)))
         (new-list (copy-list sexp)))
    (incf (jelly-ref-id j))
    (setf (car sexp) 'reference)
    (setf (cdr sexp) (list (jelly-ref-id j) new-list))
    (setf (gethash obj (jelly-cooked j)) (list 'dereference (jelly-ref-id j)))
    sexp))
    
         
(defun jelly-prepare (obj j)
(if jelly-debug (print (list "prepare" obj j) (get-buffer "*jelly-trace*")))
  (setf (gethash obj (jelly-preserved j)) (cons 'empty 'pair)))

(defun jelly-preserve (obj sexp j)
(if jelly-debug (print (list "preserve" obj sexp j) (get-buffer "*jelly-trace*")))
  (if (not (eq (gethash obj (jelly-cooked j) 'empty) 'empty))
      (progn (setf (third (gethash obj (jelly-preserved j))) sexp) 
             (gethash obj (jelly-preserved j)))
    (setf (gethash obj (jelly-preserved j)) sexp)
    sexp))
    
(defun jelly-serialize (obj j)
  (if jelly-debug (print (list "jelly-serialize" obj j) (get-buffer "*jelly-trace*")))
  "(jelly-serialise OBJECT JAR) 
    Serialises OBJECT with state JAR."
  (if (not (eq (gethash obj (jelly-cooked j) 'empty) 'empty))
      (gethash obj (jelly-cooked j))
    (if (not (eq (gethash obj (jelly-preserved j) 'empty) 'empty))
        (progn (jelly-cook obj j) 
               (gethash obj (jelly-cooked j)))
      (cond
       ((or
         (integerp obj) 
         (stringp obj) 
         (floatp obj))
        obj)
       ((or (eq obj 'None) (null obj))
        'None)
       ((hash-table-p obj)
        (jelly-prepare obj j)
        (let ((jhash '(dictionary)))
          (maphash 
           (lambda (k v) 
             (setf jhash (append jhash (list (list (jelly-serialize k j) (jelly-serialize v j))))))
             obj)
          (jelly-preserve obj jhash j)))
       
       ((listp obj)
        (jelly-prepare obj j)
        (let ((jlist (cons 'list
                           (mapcar
                            (lambda (e)
                              (jelly-serialize e j)) 
                            obj))))
           (jelly-preserve obj jlist j)))
       (t (error "Unpersistable object: %s" obj))))))

(defun jelly-serialize-alist (alist j) 
  "elisp wont tell you when a list is an alist, and it doesn't have keyword args, so i have to do something silly like this. If you use this for anything but a single top-level non-circular alist, you deserve to lose. "
  (let ((jhash '(dictionary)))
    (jelly-prepare alist j)
    (mapcar
     (lambda (pair) 
       (setf jhash (append jhash (list (list (jelly-serialize (car pair) j) (jelly-serialize (cdr pair) j))))))
     alist)
    (jelly-preserve alist jhash j)))

(defun jelly-unserialize (jelly)
  (let ((refs (make-hash-table)))
    (jelly-fixup-refs (jelly-unserialize-internal jelly))))

  

(defun jelly-unserialize-internal (jelly)
  ;; time to make dynamic scoping work for me, not against me :)
  (if (or (integerp jelly) (stringp jelly) (floatp jelly))
      jelly
    (ecase (intern (car jelly))
      ((list tuple)
       (mapcar (lambda (i) (jelly-unserialize-internal i)) (cdr jelly)))
      (dictionary
       (let ((ht (make-hash-table)))
         (mapc 
          (lambda (pair) 
            (let ((k (car pair)) (v (second pair))) ; hi glyph!
              (setf (gethash k ht) (jelly-unserialize-internal v))))
          (cdr jelly))
         ht))
      ((integer string float)
       (lambda () (cdr jelly)))
      (reference
       (let ((val  (jelly-unserialize-internal (third jelly))))
         (setf (gethash (second jelly) refs) val)
         val))
      (dereference 
       (lexical-let ((-ref-num- (cadr jelly)))
         (lambda () (gethash -ref-num- refs)))))))
  
(defun jelly-fixup-refs (obj)  
  (cond
   ((functionp obj)
    obj)
   ((or
     (integerp obj) 
     (stringp obj) 
     (floatp obj))
    obj)
   ((hash-table-p obj)
    (maphash 
     (lambda (k v)
       (if (functionp v)
           (puthash k (funcall v) obj)
         (jelly-fixup-refs v)))
     obj)
    obj)
   ((listp obj)
    (mapl 
     (lambda (list)
       (if (and (functionp (car list)) (not (compiled-function-p (car list))) (not (cadar list)))
           (setf (car list) (funcall (car list)))
         (unless (eq obj (car list)) (jelly-fixup-refs (car list)))))
     obj)
    obj)
   (t (error "it's broke"))))
   
           
            
