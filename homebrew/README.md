# Publishing to Homebrew (Cask)

To allow users to install your app using `brew install --cask videotoriso`, follow these steps:

## 1. Create a GitHub Release

1. Push your code to GitHub with a tag (e.g., `v1.0.0`).
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. The **GitHub Action** will automatically build the app, create a release, and upload `VideoToRISO.zip`.

## 2. Update the Cask

1. Once the release is ready, download the `VideoToRISO.zip` from the GitHub Release page.
2. Calculate its SHA256 hash:
   ```bash
   shasum -a 256 path/to/VideoToRISO.zip
   ```
3. Open `homebrew/videoToRISO.rb`.
4. Update the `sha256` field with the new hash.
5. Ensure the `version` matches your tag.

## 3. Create a Homebrew Tap

1. Create a new public GitHub repository named `homebrew-tap`.
2. Create a `Casks` directory in that repo.
3. Copy `homebrew/videoToRISO.rb` into the `Casks` directory of that repo (rename it to `videotoriso.rb` if you like).
4. Push the changes.

## 4. Install

Users can now install your app using:

```bash
brew tap alvinashiatey/tap
brew install --cask videotoriso
```
