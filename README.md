# Unpack 

halva2 files are simply raw brotli-compressed PAX tar archives
The CB FF bytes are just what brotli produces at quality ≥ 4.

Install python, pip install brotli

Unpack the shit out :

## Usage
`pip install brotli`

`python halva2_extract.py GamePackages/Common/DatabasePackage.halva2 -o out`
`python halva2_extract.py GamePackages/Common/AssetsPackage.halva2 -o out`
`python halva2_extract.py GamePackages/Common/AudioPackage.halva2 -o out`

`python halva2_extract.py GamePackages\win-x64\EnginePackage.halva2 -o out-win`


## And then ?
And then put stuff on a webserver that do actual brotli compress header. And please stop distributing games only for windows with weird stuff (WTF is .NET Native AOT ??)

Cheers,
