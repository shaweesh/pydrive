# Telegram File Upload and Authentication System

## Overview

This project is a web application that allows users to log in, perform two-factor authentication, and manage file uploads. It includes functionalities for:

- User authentication with phone number and 2FA (Two-Factor Authentication).
- File upload with drag-and-drop support.
- Viewing and managing uploaded files with pagination.
- Logout and navigation options.

## Project Structure

The project is organized as follows:

- **`/templates`**: Contains HTML templates.
  - **`attachments.html`**: View and manage uploaded attachments.
  - **`dashboard.html`**: Main user dashboard.
  - **`index.html`**: Login page.
  - **`two_factor.html`**: Page for two-factor authentication.
  - **`verify.html`**: Page for verifying the received code.
- **`app.py`**: Main application file containing routes and logic.
- **`config.py`**: Configuration file for storing API credentials.
- **`requirements.txt`**: List of Python packages required for the project.
- **`README.md`**: Project documentation.

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/shaweesh/pydrive
   cd pydrive
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

   - On macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:

   Ensure you have the `requirements.txt` file in your project directory. Then run:

   ```bash
   pip install -r requirements.txt
   ```

   The `requirements.txt` file includes:

   ```
   quart==0.19.6
   telethon==1.36.0
   firebase-admin==6.5.0
   aiofiles==24.1.0
   ```

## Configuration

1. **Create `config.py`** in the project root directory with the following content:

   ```python
   api_id = 'YOUR_ACTUAL_API_ID'
   api_hash = 'YOUR_ACTUAL_API_HASH'
   ```

   - Replace `'YOUR_ACTUAL_API_ID'` with the API ID you obtained from [my.telegram.org](https://my.telegram.org).
   - Replace `'YOUR_ACTUAL_API_HASH'` with the API hash you obtained from [my.telegram.org](https://my.telegram.org).

   ### Example of `config.py`

   Here's how `config.py` might look with placeholder values replaced:

   ```python
   api_id = '123456'          # Your actual API ID
   api_hash = 'abcdef123456'  # Your actual API hash
   ```

2. **Place your Firebase service account key** file as `serviceAccountKey.json` in the project root directory.

3. **Run the application**:

   ```bash
   python app.py
   ```

   The application will be available at `http://127.0.0.1:5000/`.

## Usage

1. **Login**: Open the application in your browser and enter your phone number on the login page.

2. **Two-Factor Authentication**: After entering your phone number, you'll be prompted to enter a two-factor authentication password.

3. **Dashboard**: Once authenticated, you’ll be directed to the dashboard where you can upload files and view/manage existing attachments.

4. **File Upload**: Drag and drop files or use the file picker to upload files. Files will be listed with options to download or delete.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

---

Make sure to adjust the package versions based on the exact versions you are using in your development environment.
