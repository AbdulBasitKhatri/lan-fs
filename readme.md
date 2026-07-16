# FileSharer / LAN-FS

FileSharer is a lightweight, self-hosted file sharing web app built with Python and Flask. It allows you to upload files from one device and share them with others on the same local network through a simple browser-based interface.

The project is designed for users who want a fast and practical alternative to cloud-based transfer services when they only need local-network sharing. It combines the simplicity of drag-and-drop uploads with useful controls such as password protection, expiry rules, download limits, and a separate deletion secret.

---

## Problem Statement

Traditional file sharing methods often fall short in real-world situations:

- Cloud services such as Google Drive, OneDrive, Dropbox, and WeTransfer require internet access, accounts, and sometimes file-size or storage limitations.
- Native tools like AirDrop or Nearby Share are convenient, but they are often limited to specific operating systems or ecosystems and are not ideal for sharing files to multiple users in a mixed environment.
- Traditional server-based options like FTP or SFTP can be powerful, but they are usually too technical for casual users and require complex setup.
- Many users need a quick way to share files inside a home, office, or small lab network without exposing data to the public internet.

This project addresses that gap by providing a simple, browser-based local-network file sharing solution that is:

- easy to deploy,
- easy to use,
- private by default,
- and flexible enough for temporary or controlled sharing.

---

## Why This Solution Exists

Existing solutions often optimize for either convenience or control, but not both. Cloud platforms are convenient but not always private. Native peer-to-peer tools are fast but often limited. Self-hosted servers are private but require technical effort.

FileSharer aims to provide a middle ground:

- no account required,
- no cloud dependency,
- no complex setup,
- and still enough control to protect shared files.

It is especially useful for:

- sharing files between laptops and desktops on the same LAN,
- sending work documents to coworkers without uploading them to a public service,
- distributing software or media within a small office or classroom network,
- and temporarily sharing sensitive files without permanent exposure.

---

## Comparison With Existing Solutions

| Solution | Strengths | Limitations | How FileSharer Differentiates |
|---|---|---|---|
| Google Drive / OneDrive / Dropbox | Mature, polished, cross-platform | Requires accounts, internet, and often cloud storage dependency | Runs locally on your LAN without external accounts or cloud storage |
| WeTransfer | Very simple for one-time sharing | Limited control, usually public, and not ideal for internal/private transfer | Gives password protection, expiration, download limits, and deletion control |
| AirDrop / Nearby Share | Very fast for nearby Apple or Android devices | Ecosystem-specific and not suitable for mixed-device networks | Works in a browser from any device on the same local network |
| FTP / SFTP | Powerful and flexible | Requires server configuration and technical knowledge | Provides a simple web interface with no manual server management |
| FileSharer / LAN-FS | Lightweight, local, browser-based, customizable | Best suited for local-network use rather than public internet sharing | Offers a practical balance between simplicity and control |

---

## Features

FileSharer includes the following features:

- Upload files through a web interface
- Share files using a generated link on the local network
- Optional password protection for downloads
- Separate secret deletion key for secure removal of files
- Maximum download limit support
- Time-based expiry support in seconds, minutes, hours, or days
- Automatic cleanup of expired or over-limit files
- Local storage using the filesystem and SQLite
- Simple dashboard showing active shared files and metadata

---

## How It Works

The application uses a Flask server with two storage components:

- a local folder named shared_files for the actual uploaded files
- a SQLite database named files_database.db for metadata such as filename, upload time, password hash, deletion secret hash, download count, and expiry information

When a file is uploaded:

1. the file is saved locally,
2. metadata is stored in the database,
3. a shareable link is generated for the file,
4. and optional access rules can be applied.

When a user downloads a file:

1. the app checks whether the file is still valid,
2. verifies the password if one was set,
3. increments the download count,
4. and streams the file back to the browser.

If a file reaches its expiry time or download limit, it is deleted automatically.

---

## Requirements

The app requires:

- Python 3.8 or newer
- Flask
- Werkzeug
- Jinja2

These are installed automatically through pip if you follow the setup steps below.

---

## Installation

### Windows

Open a terminal in the project folder and run:

```bash
py -3 -m venv .venv
.venv\Scripts\activate
pip install flask werkzeug jinja2
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask werkzeug jinja2
```

---

## Running the Application

From the project directory, start the server:

```bash
python main.py
```

On startup, the app will print the local IP address and the URL to use, typically:

```text
http://<your-local-ip>:5000
```

Open that address in a browser on any device connected to the same local network.

---

## Using the App

### Upload a File

1. Open the app in your browser.
2. Choose a file.
3. Optionally set:
   - an access password,
   - a deletion secret,
   - a download limit,
   - and an expiry duration.
4. Click the upload button.

### Share a File

After upload, the app displays a shareable link for the file. Copy that link and send it to the recipient on the same network.

### Download a File

- Public files can be downloaded directly.
- Password-protected files require the password before download begins.

### Delete a File

Use the delete action and provide the matching secret deletion key. This removes the file from the local storage and the database record.

---

## Configuration Notes

The application uses the following defaults:

- upload directory: shared_files
- database: files_database.db
- server port: 5000
- host binding: 0.0.0.0

The maximum upload size is set to 500 MB by default.

---

## Security Considerations

This application is intended for local-network sharing and provides useful access control, but it is not a full enterprise-grade encryption platform.

Important notes:

- Passwords are hashed using Werkzeug.
- Files are stored locally on disk.
- The app is best used inside a trusted local network.
- If you need stronger protection for highly sensitive data, consider adding client-side encryption before uploading.

---

## Project Structure

```text
FileSharer/
├── main.py
├── readme.md
├── shared_files/          # uploaded files are stored here
└── files_database.db      # SQLite database created at runtime
```

---

## Future Improvements

Possible enhancements for future versions include:

- user accounts and role-based access
- chunked uploads for very large files
- HTTPS support for secure local deployment
- drag-and-drop UI improvements
- file previews and richer metadata
- optional end-to-end encryption

---

## Summary

FileSharer is a practical and lightweight local-network file sharing tool for users who want control without the overhead of complex server setup. It fills the gap between casual cloud transfers and technical self-hosted servers by offering a fast, browser-based, private, and flexible sharing experience.

If you want a simple way to share files inside your home or office network without relying on public cloud platforms, this project is a strong starting point.
