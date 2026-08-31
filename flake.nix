{
  description = "murchace";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # <https://github.com/nix-systems/nix-systems>
    systems.url = "github:nix-systems/default";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv-python.url = "github:pyproject-nix/uv-python.nix";
    uv-python.inputs.nixpkgs.follows = "nixpkgs";
    pyproject-build-systems.url = "github:pyproject-nix/build-system-pkgs";
    pyproject-build-systems.inputs = {
      pyproject-nix.follows = "pyproject-nix";
      uv2nix.follows = "uv2nix";
      nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      systems,
      pyproject-nix,
      uv2nix,
      uv-python,
      pyproject-build-systems,
      self,
    }:
    let
      perSystem =
        cb:
        nixpkgs.lib.genAttrs (import systems) (
          system:
          cb (
            {
              pkgs = nixpkgs.legacyPackages.${system};
            }
            // nixpkgs.lib.attrsets.concatMapAttrs (
              key: value: if value ? ${system} then { ${key} = value.${system}; } else { }
            ) self.outputs
          )
        );
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
    in
    {
      inherit self;
      inherit workspace;

      packages = perSystem (
        { pkgs, ... }:
        let
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages {
              python =
                uv-python.packages.${pkgs.stdenv.hostPlatform.system}."cpython-${pkgs.lib.fileContents ./.python-version}";
            }).overrideScope
              (
                pkgs.lib.composeManyExtensions [
                  pyproject-build-systems.overlays.wheel
                  (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
                ]
              );
          venv = pythonSet.mkVirtualEnv "murchace-venv" workspace.deps.default;
        in
        {
          default = pkgs.writeShellApplication {
            name = "murchace";
            runtimeInputs = [ venv ];
            text = ''
              # shellcheck disable=SC2068
              doit serve $@
            '';
          };
          inherit pythonSet;
        }
      );

      devShells = perSystem (
        { pkgs, packages, ... }:
        let
          editablePythonSet = packages.pythonSet.overrideScope (
            workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; }
          );
          venv = editablePythonSet.mkVirtualEnv "murchace-venv-editable" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              venv
              pkgs.uv
              pkgs.sqlite
              pkgs.tailwindcss_4
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = editablePythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
              UV_PROJECT_ENVIRONMENT = "${venv}";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
              # https://discourse.nixos.org/t/fix-ssl-sslcertverificationerror-with-uvs-standalone-python/71138
              export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt;
              export NIX_SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt;
              . ${venv}/bin/activate
            '';
          };
        }
      );
    };
}
