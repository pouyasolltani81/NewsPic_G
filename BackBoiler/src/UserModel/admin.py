from django.contrib import admin
from .models import User

class UserAdmin(admin.ModelAdmin):
    list_display=('id', 'uuid', 'is_staff', 'is_superuser', 'is_active' , 'username',  'email', 'password', 'date_joined', 'last_login')

    fieldsets = (
        ('New User', {'fields': ('is_active', 'uuid', 'username', 'email', 'password',)}),
        ('Dates', {'fields': ('last_login', 'date_joined')})
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'is_active')}
         ),
    )
    search_fields = ('email', 'username', 'id', 'uuid')
    ordering = ('id',)

    def save_model(self, request, obj, form, change):
        
        if 'password' in form.changed_data:
            obj.set_password(obj.password)
            
        super().save_model(request, obj, form, change)


admin.site.register(User,UserAdmin)
