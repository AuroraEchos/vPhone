#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
sdk_root=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}

if [[ -z "$sdk_root" ]]; then
    echo "Set ANDROID_HOME or ANDROID_SDK_ROOT to an Android SDK." >&2
    exit 1
fi

platform_dir=$(find "$sdk_root/platforms" -mindepth 1 -maxdepth 1 -type d -name 'android-*' | sort -V | tail -1)
if [[ -z "$platform_dir" ]]; then
    echo "No Android SDK platform was found under $sdk_root/platforms." >&2
    exit 1
fi

d8_path=$(find "$sdk_root" -type f -name d8 2>/dev/null | sort -V | tail -1)
if [[ -z "$d8_path" ]]; then
    echo "The Android d8 tool was not found under $sdk_root." >&2
    exit 1
fi

build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT

android_jar="$platform_dir/android.jar"
uiautomator_jar="$platform_dir/uiautomator.jar"
source_file="$project_dir/android/unicode-input/src/dev/vphone/UnicodeInputTest.java"
stub_file="$project_dir/android/unicode-input/compile-stubs/junit/framework/TestCase.java"
output_file="$project_dir/src/vphone/device/adb/resources/vphone-unicode-input.jar"

mkdir -p "$build_dir/classes" "$build_dir/stubs" "$(dirname -- "$output_file")"
javac \
    -source 8 \
    -target 8 \
    -bootclasspath "$android_jar" \
    -d "$build_dir/stubs" \
    "$stub_file"
javac \
    -source 8 \
    -target 8 \
    -bootclasspath "$android_jar:$uiautomator_jar" \
    -classpath "$build_dir/stubs" \
    -d "$build_dir/classes" \
    "$source_file"
jar --create --file "$build_dir/compile-stubs.jar" -C "$build_dir/stubs" .
jar --create --file "$build_dir/unicode-input-classes.jar" -C "$build_dir/classes" .
"$d8_path" \
    --lib "$android_jar" \
    --lib "$uiautomator_jar" \
    --lib "$build_dir/compile-stubs.jar" \
    --output "$output_file" \
    "$build_dir/unicode-input-classes.jar"

echo "Built $output_file"
