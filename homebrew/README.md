# Publishing to Homebrew

To allow users to install your app using `brew install videoToRISO`, follow these steps:

## 1. Create a GitHub Release

1. Push your code to GitHub.
2. Go to "Releases" > "Draft a new release".
3. Tag it `v1.0.0`.
4. Publish the release.
5. Copy the link to the "Source code (tar.gz)".

## 2. Update the Formula

1. Open `homebrew/videoToRISO.rb`.
2. Update `homepage` and `url` with your GitHub repository details.
3. Download the tar.gz file you just released and calculate its SHA256 hash:
   ```bash
   shasum -a 256 path/to/v1.0.0.tar.gz
   ```
4. Update the `sha256` field in `videoToRISO.rb` with this hash.

## 3. Create a Homebrew Tap

1. Create a new public GitHub repository named `homebrew-tap` (or `homebrew-videoToRISO`).
2. Add the `videoToRISO.rb` file to the root of this new repository.
3. Push the changes.

## 4. Install

Users can now install your app using:

```bash
brew tap YOUR_USERNAME/tap
brew install videoToRISO
```

## Note on Dependencies

This formula uses a virtual environment to install the Python dependencies defined in your `setup.py`. This ensures they don't conflict with system Python packages.
