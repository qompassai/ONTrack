# vi: ft=nix
{
  description = "OnTrack — TDS field technician productivity app for Android";
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = {
    flake-utils,
    nixpkgs,
    rust-overlay,
    ...
  }:
    flake-utils.lib.eachSystem [
      "x86_64-linux"
    ] (
      system: let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          overlays = [
            rust-overlay.overlays.default
          ];
        };
        rustToolchain = pkgs.rust-bin.stable.latest.default.override {
          extensions = [
            "rust-src"
            "rust-analyzer"
            "clippy"
          ];
        };
        androidSdkRoot = "/opt/android-sdk";
        androidNdkRoot = "/opt/android-sdk/ndk/29.0.14206865";
        meta = with pkgs.lib; {
          broken = false;
          changelog = "https://github.com/qompassai/Python/blob/main/ontrack/CHANGELOG.md";
          description = "OnTrack Android productivity app for field service technicians";
          downloadPage = "https://github.com/qompassai/Python/releases";
          homepage = "https://github.com/qompassai/Python/tree/main/ontrack";
          hydraPlatforms = [];
          license = licenses.unfree;
          longDescription = ''
            OnTrack is a Kivy-based Android application built for TDS field
            technicians. It provides location-aware job tracking, offline-capable
            workflows, and streamlined field reporting for armeabi-v7a and
            arm64-v8a targets. Built with python-for-android and Buildozer.
          '';
          maintainers = [
            "Qompass AI"
          ];
          platforms = [
            "x86_64-linux"
          ];
          sourceProvenance = with sourceTypes; [
            binaryBytecode
            binaryNativeCode
            fromSource
          ];
        };
      in {
        devShells.default = pkgs.mkShell {
          name = "ontrack-buildozer";
          inherit meta;
          ANDROID_HOME = androidSdkRoot;
          ANDROID_SDK_ROOT = androidSdkRoot;
          ANDROID_NDK_HOME = androidNdkRoot;
          ANDROID_NDK_ROOT = androidNdkRoot;
          ANDROID_NDK_VERSION = "r29";
          JAVA_HOME = "${pkgs.jdk17}";
          JAVA_TOOL_OPTIONS = "";
          _JAVA_OPTIONS = "";
          PIP_CONFIG_FILE = "/dev/null";
          BUILDOZER_BUILD_DIR = "/var/tmp/buildozer/ontrack/build";
          BUILDOZER_BIN_DIR = "/var/tmp/buildozer/ontrack/bin";
          TMPDIR = "/var/tmp/buildozer/tmp";
          TEMP = "/var/tmp/buildozer/tmp";
          TMP = "/var/tmp/buildozer/tmp";
          CCACHE_TEMPDIR = "/var/tmp/buildozer/tmp";
          buildInputs = with pkgs; [
            jdk17
            python312
            python312Packages.cython
            python312Packages.pip
            python312Packages.virtualenv
            autoconf
            automake
            cmake
            curl
            git
            libtool
            ninja
            unzip
            which
            zlib
            libffi
            openssl
            sqlite
          ];
          shellHook = ''
            echo "OnTrack build env"
            echo "  Java    : $(java -version 2>&1 | head -1)"
            echo "  NDK     : $ANDROID_NDK_ROOT"
            echo "  SDK     : $ANDROID_SDK_ROOT"
            echo "  TMPDIR  : $TMPDIR"
            if [ ! -f "$ANDROID_NDK_ROOT/ndk-build" ]; then
              echo "  WARNING: NDK not found at $ANDROID_NDK_ROOT"
            fi
            if [ ! -d "$ANDROID_SDK_ROOT/platform-tools" ]; then
              echo "  WARNING: Android SDK incomplete at $ANDROID_SDK_ROOT"
            fi
            mkdir -p "$BUILDOZER_BUILD_DIR" "$BUILDOZER_BIN_DIR" "$TMPDIR"

            export PATH="$(echo "$PATH" | tr ':' '\n' | grep -vE '(ccache|java-25|jdk-[^1]|jre-)' | tr '\n' ':')"
            export PATH="${pkgs.jdk17}/bin:$PATH"
            export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/tools/bin:$PATH"
            if [ ! -d .venv-buildozer ]; then
              echo "  Creating buildozer venv..."
              python -m venv .venv-buildozer
              .venv-buildozer/bin/pip install --quiet --upgrade pip
              .venv-buildozer/bin/pip install --quiet buildozer cython
            fi
            source .venv-buildozer/bin/activate
            echo "  Python  : $(python --version)"
            echo "  Buildozer: $(buildozer --version 2>/dev/null || echo 'not installed')"
            echo ""
            echo "  Ready. Run: buildozer android debug"
          '';
        };
        devShells.maturin = pkgs.mkShell {
          name = "ontrack-maturin";
          RUST_BACKTRACE = "1";
          RUST_SRC_PATH = "${rustToolchain}/lib/rustlib/src/rust/library";
          buildInputs = with pkgs; [
            maturin
            python312
            python312Packages.pip
            python312Packages.virtualenv
            rustToolchain
            pkg-config
            openssl
            zlib
          ];
          shellHook = ''
            echo "OnTrack maturin/Rust dev env"
            echo "  Rust    : $(rustc --version)"
            echo "  Cargo   : $(cargo --version)"
            echo "  Maturin : $(maturin --version)"
            echo "  Python  : $(python3 --version)"
            if [ ! -d .venv-maturin ]; then
              echo "  Creating maturin venv..."
              python3 -m venv .venv-maturin
              .venv-maturin/bin/pip install --quiet --upgrade pip
            fi
            source .venv-maturin/bin/activate
            echo ""
            echo "  Ready. Run: maturin develop"
          '';
        };
      }
    );
}
