

$ django-codegen model Blog title:CharField content:TextField:blank:null

generates

    # blogs/models.py

    from django.db import models


    class Blog(models.Model):
        class Meta:
            verbose_name = "Blog"
            verbose_name_plural = "Blogs"

        title = models.CharField(max_length=250)

        content = models.TextField(blank=True, null=True)


    # blogs/admin.py

    from django.contrib import admin

    from .models import Blog


    @admin.register(Blog)
    class BlogAdmin(admin.ModelAdmin):
        pass



# Features/ideas 

- Generators:
    - model (with ModelAdmin)
    - view (with URLConfs)

- Uses black https://black.readthedocs.io/en/stable/reference/reference_summary.html

- Interactive mode

- Config via pyproject.toml
    - Set a default model class to inherit from (ie. CreatedUpdatedModel etc.)
    
# Notes:

- Look at https://docs.python.org/3.8/library/ast.html for manipulating existing files