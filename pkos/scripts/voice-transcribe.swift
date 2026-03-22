import Foundation
import Speech

// MARK: - Language Detection

func detectLanguage(from filename: String) -> String {
    let base = (filename as NSString).lastPathComponent
    if base.hasPrefix("en-") { return "en-US" }
    if base.hasPrefix("zh-") { return "zh-CN" }
    return "en-US" // default to English
}

// MARK: - Apple Speech (on-device for en-US, online for zh-CN)

func transcribeAppleSpeech(fileURL: URL, localeId: String) -> String? {
    let recognizer = SFSpeechRecognizer(locale: Locale(identifier: localeId))
    guard let recognizer = recognizer, recognizer.isAvailable else {
        fputs("Error: SFSpeechRecognizer not available for \(localeId)\n", stderr)
        return nil
    }

    let request = SFSpeechURLRecognitionRequest(url: fileURL)
    request.shouldReportPartialResults = false

    var resultText: String?
    var resultError: Error?
    let semaphore = DispatchSemaphore(value: 0)

    recognizer.recognitionTask(with: request) { result, error in
        if let error = error {
            resultError = error
            semaphore.signal()
            return
        }
        guard let result = result else {
            semaphore.signal()
            return
        }
        if result.isFinal {
            resultText = result.bestTranscription.formattedString
            semaphore.signal()
        }
    }

    let timeout = semaphore.wait(timeout: .now() + 120) // 2 min timeout
    if timeout == .timedOut {
        fputs("Error: Transcription timed out after 120s\n", stderr)
        return nil
    }
    if let error = resultError {
        fputs("Error: \(error.localizedDescription)\n", stderr)
        return nil
    }
    return resultText
}

// MARK: - Whisper (offline, for zh-CN primary)

func transcribeWhisper(fileURL: URL) -> String? {
    let searchPaths = [
        "/opt/homebrew/bin/mlx_whisper",
        "/opt/homebrew/bin/whisper-cpp",
        "/usr/local/bin/mlx_whisper",
        "/usr/local/bin/whisper-cpp",
    ]

    for cmdPath in searchPaths {
        guard FileManager.default.fileExists(atPath: cmdPath) else { continue }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: cmdPath)
        proc.arguments = [fileURL.path]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice
        do {
            try proc.run()
            proc.waitUntilExit()
            if proc.terminationStatus == 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
            }
        } catch {
            continue
        }
    }
    return nil
}

// MARK: - Chinese with Fallback (DP-001 Chosen B)

func transcribeChineseWithFallback(fileURL: URL) -> String? {
    // Try Whisper first (offline)
    if let whisperResult = transcribeWhisper(fileURL: fileURL) {
        return whisperResult
    }
    // Fallback: Apple Speech online for zh-CN (requires network)
    fputs("Warning: Whisper unavailable, falling back to Apple Speech online (zh-CN)\n", stderr)
    return transcribeAppleSpeech(fileURL: fileURL, localeId: "zh-CN")
}

// MARK: - Main

func printUsage() {
    let prog = CommandLine.arguments[0]
    fputs("Usage: \(prog) <audio-file>\n", stderr)
    fputs("  Transcribes audio file to text.\n", stderr)
    fputs("  Language detected from filename prefix: en-* → Apple Speech, zh-* → Whisper (fallback: Apple Speech online)\n", stderr)
    fputs("  Output: transcribed text on stdout\n", stderr)
}

guard CommandLine.arguments.count >= 2 else {
    printUsage()
    exit(1)
}

let arg = CommandLine.arguments[1]
if arg == "--help" || arg == "-h" {
    printUsage()
    exit(0)
}

let filePath = arg
let fileURL = URL(fileURLWithPath: filePath)

guard FileManager.default.fileExists(atPath: filePath) else {
    fputs("Error: File not found: \(filePath)\n", stderr)
    exit(1)
}

// Request authorization
SFSpeechRecognizer.requestAuthorization { status in
    guard status == .authorized else {
        fputs("Error: Speech recognition not authorized (status: \(status.rawValue))\n", stderr)
        exit(2)
    }
}

// Small delay to allow authorization callback
Thread.sleep(forTimeInterval: 0.5)

let lang = detectLanguage(from: filePath)
var transcript: String?

if lang == "zh-CN" {
    transcript = transcribeChineseWithFallback(fileURL: fileURL)
} else {
    transcript = transcribeAppleSpeech(fileURL: fileURL, localeId: lang)
}

guard let text = transcript, !text.isEmpty else {
    fputs("Error: Transcription failed or returned empty result\n", stderr)
    exit(3)
}

print(text)
