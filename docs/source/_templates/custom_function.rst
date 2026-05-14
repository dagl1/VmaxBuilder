.. rubric:: {{ module.split('.')[-1] + '.' + name + '()' }}
   :heading-level: {{ 2 if (module.split('.')[-1] + '.' + name + '()')|length > 20 else 1 }}

.. currentmodule:: {{ module }}

.. auto{{ objtype }}:: {{ objname }}
