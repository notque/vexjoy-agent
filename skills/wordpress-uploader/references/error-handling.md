# WordPress Uploader Error Handling

## Error: "WORDPRESS_SITE not set" or Missing Credentials
Cause: Environment variables not configured in `~/.env`
Solution:
1. Verify `~/.env` exists in the home directory
2. Check it contains WORDPRESS_SITE, WORDPRESS_USER, and WORDPRESS_APP_PASSWORD
3. Ensure no extra whitespace or quoting around values

## Error: "401 Unauthorized"
Cause: Invalid or expired Application Password
Solution:
1. Log into WordPress admin (wp-admin) > Users > Profile
2. Revoke the old Application Password
3. Generate a new one and update `~/.env`
4. Verify the username matches the WordPress account exactly

## Error: "403 Forbidden"
Cause: WordPress user lacks required capability (e.g., publish_posts, upload_files)
Solution:
1. Confirm the user has Editor or Administrator role
2. Check if a security plugin is blocking REST API access
3. Verify the site allows Application Password authentication

## Error: "File not found" or Empty Content
Cause: Incorrect file path or markdown file is empty
Solution:
1. Verify the file path with `ls -la <path>`
2. Confirm the file has content (not zero bytes)
3. Check for typos in the path, especially the content/ directory structure
