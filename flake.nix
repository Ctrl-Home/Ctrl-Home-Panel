{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
      in
      {
        packages.default = pkgs.python3Packages.buildPythonApplication {
          pname = "p2p-fs";
          version = "0.1.2";
          src = ./.;
          format = "setuptools";

          # 创建setup.py文件
          preBuild = ''
            cat > setup.py << EOF
            from setuptools import setup
            
            setup(
                name="p2p-fs",
                version="0.1.2",
                py_modules=["p2p_fs"],
                entry_points={
                    "console_scripts": [
                        "p2p-fs=p2p_fs:main",
                    ],
                },
            )
            EOF
          '';
          
          meta = {
            description = "A P2P File System implementation in Python";
            license = pkgs.lib.licenses.mit;
            platforms = pkgs.lib.platforms.all;
          };
        };
        
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python3
            pkgs.python3Packages.virtualenv
          ];
          shellHook = ''
            # 设置虚拟环境目录
            VENV_DIR=".venv"

            # 创建虚拟环境（如果不存在）
            if [ ! -d "$VENV_DIR" ]; then
              python -m virtualenv "$VENV_DIR"
            fi

            # 激活虚拟环境
            source "$VENV_DIR/bin/activate"

            echo "🚀Virtual environment activated."
          '';
        };
      }
    );
}
# nix develop
