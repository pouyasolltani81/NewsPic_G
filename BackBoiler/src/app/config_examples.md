# 🎨 Configuration Examples

This file shows practical examples of how to customize your TempBoiler project using the `editConfig` command.

## 🏷️ Project Identity Customization

### Change Project Name
```bash
# Change the internal project name
python src/manage.py editConfig --key "project.name" --value "MyAwesomeApp"

# Change the display name (shown to users)
python src/manage.py editConfig --key "project.display_name" --value "MyAwesomeApp"

# Update project description
python src/manage.py editConfig --key "project.description" --value "A powerful web application for managing awesome things"
```

### Update Author Information
```bash
# Change author name
python src/manage.py editConfig --key "project.author" --value "Your Name"

# Update contact email
python src/manage.py editConfig --key "project.email" --value "your.email@example.com"

# Set your website
python src/manage.py editConfig --key "project.website" --value "https://yourwebsite.com"
```

## 📚 API Documentation Customization

### Update API Title and Description
```bash
# Change API title (shown in Swagger UI)
python src/manage.py editConfig --key "api.title" --value "MyAwesomeApp API"

# Update API description
python src/manage.py editConfig --key "api.description" --value "Complete API documentation for MyAwesomeApp"

# Set API version
python src/manage.py editConfig --key "api.version" --value "v2.0"
```

### Update Contact Information
```bash
# Set contact person
python src/manage.py editConfig --key "api.contact_name" --value "Your Name"

# Set contact email
python src/manage.py editConfig --key "api.contact_email" --value "api@yourapp.com"
```

## 🎨 UI Customization

### Theme and Language
```bash
# Change default theme
python src/manage.py editConfig --key "ui.theme" --value "dark"

# Set default language
python src/manage.py editConfig --key "ui.default_language" --value "fa"

# Update supported languages
python src/manage.py editConfig --key "ui.supported_languages" --value "[en, fa, es]"
```

### Branding Colors
```bash
# Set primary color
python src/manage.py editConfig --key "ui.primary_color" --value "#FF6B6B"

# Set secondary color
python src/manage.py editConfig --key "ui.secondary_color" --value "#4ECDC4"
```

## 📊 Analytics Configuration

### Enable/Disable Features
```bash
# Disable analytics completely
python src/manage.py editConfig --key "analytics.enabled" --value "false"

# Enable analytics with sampling
python src/manage.py editConfig --key "analytics.sample_rate" --value "0.5"

# Disable GeoIP tracking
python src/manage.py editConfig --key "analytics.geoip_enabled" --value "false"
```

## 🔒 Security Settings

### Debug and Hosts
```bash
# Disable debug mode for production
python src/manage.py editConfig --key "security.debug" --value "false"

# Restrict allowed hosts
python src/manage.py editConfig --key "security.allowed_hosts" --value "[localhost, yourdomain.com]"

# Disable CORS
python src/manage.py editConfig --key "security.cors_enabled" --value "false"
```

## 🗄️ Database Configuration

### Update Database URLs
```bash
# Change main database
python src/manage.py editConfig --key "database.default" --value "postgresql://user:pass@localhost/dbname"

# Update logs database
python src/manage.py editConfig --key "database.logs" --value "postgresql://user:pass@localhost/logs"
```

## 🚀 Complete Project Makeover Example

Here's how to completely rebrand your project in one go:

```bash
# 1. Update project identity
python src/manage.py editConfig --key "project.name" --value "EcommercePro"
python src/manage.py editConfig --key "project.display_name" --value "EcommercePro"
python src/manage.py editConfig --key "project.description" --value "Professional e-commerce platform with advanced analytics"

# 2. Update API documentation
python src/manage.py editConfig --key "api.title" --value "EcommercePro API"
python src/manage.py editConfig --key "api.description" --value "Complete API for EcommercePro platform"

# 3. Customize UI
python src/manage.py editConfig --key "ui.theme" --value "dark"
python src/manage.py editConfig --key "ui.primary_color" --value "#FF6B6B"
python src/manage.py editConfig --key "ui.secondary_color" --value "#4ECDC4"

# 4. Update author info
python src/manage.py editConfig --key "project.author" --value "Your Company Name"
python src/manage.py editConfig --key "project.email" --value "contact@ecommercepro.com"
python src/manage.py editConfig --key "project.website" --value "https://ecommercepro.com"
```

## 🔄 Reset and Restore

### Reset to Defaults
```bash
# Reset all configuration to TempBoiler defaults
python src/manage.py editConfig --reset
```

### View Current Configuration
```bash
# Show all current settings
python src/manage.py editConfig --show

# List all available keys
python src/manage.py editConfig --list
```

## 💡 Pro Tips

1. **Backup First**: Always backup your `config.json` before making changes
2. **Test Changes**: Restart your Django server after configuration changes
3. **Use Interactive Mode**: Run `python src/manage.py editConfig` for guided editing
4. **Version Control**: Commit your `config.json` to track configuration changes
5. **Environment Specific**: Consider having different config files for dev/staging/prod

## 🎯 What Gets Updated Automatically

When you change values in `config.json`, these are automatically updated:

- ✅ **Welcome Pages** - Project names and descriptions
- ✅ **Page Titles** - Browser tab titles
- ✅ **API Documentation** - Swagger/OpenAPI interface
- ✅ **Footer Information** - Copyright and branding
- ✅ **System Settings** - Debug mode, allowed hosts
- ✅ **UI Preferences** - Theme, language, colors
- ✅ **Analytics Settings** - Feature toggles and rates

## 🚨 Important Notes

- **Server Restart**: Some changes require restarting the Django server
- **Cache**: Configuration is cached for 5 minutes for performance
- **Validation**: The system automatically validates data types
- **Fallbacks**: Default values are used if configuration is invalid
- **Security**: Sensitive settings like SECRET_KEY should still use environment variables
