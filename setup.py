from setuptools import setup, find_packages

setup(
    name="videoToRISO",
    version="1.0.0",
    description="A tool to convert video frames into RISO-ready contact sheets.",
    author="Alvin Kwabena",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "opencv-python",
        "Pillow",
        "numpy",
        "customtkinter",
        "packaging"
    ],
    entry_points={
        'console_scripts': [
            'videoToRISO=app.app:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
