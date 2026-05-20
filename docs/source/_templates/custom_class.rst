.. rubric:: {{ name }}
   :heading-level: 1


.. currentmodule:: {{ module }}

.. autoclass:: {{ objname }}
   :members:
   :exclude-members: define_local

   {% block methods %}
   {% set allmethods = methods %}
   {% if methods %}

   .. rubric:: {{ _('Public Methods') }}

   .. autosummary::
      :signatures: {{ 'short' }}
      :template: custom_method.rst
      {% for item in methods if not item.startswith('__init__') %}
         {% if 'define_local' not in item %}
            {{ item.split('.')[-1] }}
            ~{{ ' ' }}
         {% endif %}
      {%  endfor %}
   {% endif %}
   {% endblock %}



   {% block private_methods %}
   {% set privatemethods = allmethods | select('search', '^_') | list %}
   {% if privatemethods %}

   .. rubric:: {{ _('Private Methods') }}

   .. autosummary::
      :template: empty_custom_method.rst
      {% for item in privatemethods if not item.startswith('__init__') %}
         {% if 'define_local' not in item %}
            {{ item.replace('ModelPreprocessor,', '') }}

            ~{{ ' ' }}

            ~{{ ' ' }}
         {% endif %}
      {%  endfor %}
   {% endif %}
   {% endblock %}

   {% block attributes %}
   {% if attributes %}
      {% set areAttributes = true %}
         {% if attributes | length == 1 and attributes[0] == 'all_keywords' %}
         {% set areAttributes = false %}
      {% endif %}
      {% if areAttributes %}

      .. rubric:: {{ _('Attributes') }}

      .. autosummary::

         {% for item in attributes %}
           {% if item != 'all_keywords' %}
               ~{{ item }}
            {% endif %}
         {%- endfor %}

   {% endif %}
   {% endif %}
   {% endblock %}
