{# Use the custom schema name as-is (default dbt prefixes it with the target schema) #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}
    {%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
