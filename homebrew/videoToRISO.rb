class Videotoriso < Formula
  include Language::Python::Virtualenv

  desc "A tool to convert video frames into RISO-ready contact sheets"
  homepage "https://github.com/YOUR_USERNAME/videoToRISO"
  url "https://github.com/YOUR_USERNAME/videoToRISO/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_OF_YOUR_TARBALL"
  license "MIT"

  depends_on "python@3.11"
  # Add system dependencies if needed, e.g.
  # depends_on "opencv"

  def install
    # Create a virtualenv in libexec and install dependencies
    virtualenv_create(libexec, "python3.11")
    
    # Install the package
    system libexec/"bin/pip", "install", "-v", "."
    
    # Link the executable to bin
    bin.install_symlink libexec/"bin/videoToRISO"
  end

  test do
    # Simple test to check if import works
    system libexec/"bin/python", "-c", "import app.app"
  end
end
