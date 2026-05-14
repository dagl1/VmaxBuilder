{% set short = name.replace('SWAMP.', '') %}
{{ short | escape | underline }}

.. currentmodule:: {{ module }}

.. automodule:: {{ fullname }}

   {% block classes %}
   {% if classes %}
      .. rubric:: {{ _('Classes') }}

      .. autosummary::
         :template: custom_class.rst
         :toctree:
         {% for item in classes %}
            {% if not item.startswith('__init__') %}
               {{ item }}
            {% endif %}
         {% endfor %}
   {% endif %}
   {% endblock %}

   {% block functions %}
   {% if functions %}
      .. rubric:: {{ _('Functions') }}

      .. autosummary::
         :toctree: generated/
         :template: custom_function.rst

         {% for item in functions %}
            {% if not item.startswith('__init__') %}
               {{ item }}
            {% endif %}
         {%- endfor %}
      {% endif %}
      {% endblock %}

   {% block methods %}
   {% if methods %}
      .. rubric:: {{ _('Methods') }}

      .. autosummary::
         :toctree:

         {% for item in methods %}
         {% if not item.endswith('__init__()') and not item.startswith('Model') %}
            {{ item }}
         {% endif %}
         {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block attributes %}
   {% if attributes %}
      .. rubric:: {{ _('Attributes') }}

      .. autosummary::
         :template: custom_attribute.rst
         :toctree:

         {% for item in attributes %}
            {% if not item.endswith('__init__()') and not item.startswith('Model') %}
               {{ item }}
            {% endif %}
         {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block modules %}
   {% if modules %}
      .. rubric:: Modules

      .. autosummary::
         :toctree:
         :template: custom_sub_module.rst

         {% for item in modules %}
         {% if not item.endswith('__init__()') and not item.startswith('Model') %}
            {{ item }}
         {% endif %}
         {% endfor %}
   {% endif %}
   {% endblock %}
