#!/usr/bin/env swift

import Foundation
import Vision
import AppKit
import CoreGraphics
import PDFKit

// MARK: - Configuration

struct OCRConfig {
    var filePath: String = ""
    var languages: [String] = ["zh-Hans", "en-US"]
    var maxPages: Int = 20
}

// MARK: - Argument Parsing

func parseArguments() -> OCRConfig {
    var config = OCRConfig()
    let args = CommandLine.arguments

    guard args.count >= 2 else {
        printUsage()
        exit(1)
    }

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--lang":
            i += 1
            guard i < args.count else {
                fputs("Error: --lang requires a value (e.g., zh-Hans,en-US)\n", stderr)
                exit(1)
            }
            config.languages = args[i].split(separator: ",").map(String.init)
        case "--max-pages":
            i += 1
            guard i < args.count, let val = Int(args[i]), val > 0 else {
                fputs("Error: --max-pages requires a positive integer\n", stderr)
                exit(1)
            }
            config.maxPages = val
        case "--help", "-h":
            printUsage()
            exit(0)
        default:
            if args[i].hasPrefix("-") {
                fputs("Error: Unknown option '\(args[i])'\n", stderr)
                printUsage()
                exit(1)
            }
            config.filePath = args[i]
        }
        i += 1
    }

    guard !config.filePath.isEmpty else {
        fputs("Error: No file path provided\n", stderr)
        printUsage()
        exit(1)
    }

    return config
}

func printUsage() {
    let usage = """
    Usage: ocr <file_path> [options]

    Extract text from images and scanned PDFs using macOS Vision framework.

    Supported image formats: png, jpg, jpeg, tiff, bmp, gif, heic
    Supported document formats: pdf

    Options:
      --lang <languages>     Comma-separated recognition languages (default: zh-Hans,en-US)
      --max-pages <n>        Maximum PDF pages to process (default: 20)
      --help, -h             Show this help message

    Examples:
      ocr screenshot.png
      ocr document.pdf --lang en-US --max-pages 10
      ocr photo.heic --lang zh-Hans,en-US,ja
    """
    fputs(usage + "\n", stderr)
}

// MARK: - File Validation

let supportedImageExtensions: Set<String> = ["png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif", "heic"]

func resolveFilePath(_ path: String) -> String {
    let expanded = NSString(string: path).expandingTildeInPath
    if expanded.hasPrefix("/") {
        return expanded
    }
    return FileManager.default.currentDirectoryPath + "/" + expanded
}

func validateFile(_ path: String) -> (fullPath: String, isPDF: Bool) {
    let fullPath = resolveFilePath(path)

    guard FileManager.default.fileExists(atPath: fullPath) else {
        fputs("Error: File not found: \(fullPath)\n", stderr)
        exit(1)
    }

    let ext = (fullPath as NSString).pathExtension.lowercased()

    if ext == "pdf" {
        return (fullPath, true)
    }

    guard supportedImageExtensions.contains(ext) else {
        fputs("Error: Unsupported file format '.\(ext)'\n", stderr)
        fputs("Supported formats: \(supportedImageExtensions.sorted().joined(separator: ", ")), pdf\n", stderr)
        exit(1)
    }

    return (fullPath, false)
}

// MARK: - OCR Engine

func performOCR(on cgImage: CGImage, languages: [String]) -> String {
    let semaphore = DispatchSemaphore(value: 0)
    var resultText = ""
    var ocrError: Error?

    let request = VNRecognizeTextRequest { request, error in
        defer { semaphore.signal() }

        if let error = error {
            ocrError = error
            return
        }

        guard let observations = request.results as? [VNRecognizedTextObservation] else {
            return
        }

        let lines = observations.compactMap { observation -> String? in
            observation.topCandidates(1).first?.string
        }

        resultText = lines.joined(separator: "\n")
    }

    request.recognitionLevel = .accurate
    request.recognitionLanguages = languages
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

    do {
        try handler.perform([request])
    } catch {
        fputs("Error: Vision request failed: \(error.localizedDescription)\n", stderr)
        return ""
    }

    semaphore.wait()

    if let error = ocrError {
        fputs("Warning: OCR error: \(error.localizedDescription)\n", stderr)
    }

    return resultText
}

// MARK: - Image OCR

func ocrImage(at path: String, languages: [String]) -> String {
    let url = URL(fileURLWithPath: path)

    guard let imageSource = CGImageSourceCreateWithURL(url as CFURL, nil),
          let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
        fputs("Error: Failed to load image: \(path)\n", stderr)
        exit(1)
    }

    return performOCR(on: cgImage, languages: languages)
}

// MARK: - PDF OCR

func ocrPDF(at path: String, languages: [String], maxPages: Int) -> String {
    let url = URL(fileURLWithPath: path)

    guard let pdfDocument = PDFDocument(url: url) else {
        fputs("Error: Failed to open PDF: \(path)\n", stderr)
        exit(1)
    }

    let pageCount = pdfDocument.pageCount
    let pagesToProcess = min(pageCount, maxPages)

    if pageCount > maxPages {
        fputs("[Info] PDF has \(pageCount) pages, processing first \(maxPages) (use --max-pages to adjust)\n", stderr)
    }

    var allText: [String] = []

    for pageIndex in 0..<pagesToProcess {
        guard let page = pdfDocument.page(at: pageIndex) else {
            fputs("Warning: Failed to load page \(pageIndex + 1)\n", stderr)
            continue
        }

        // First try to extract embedded text from the PDF page
        let embeddedText = page.string ?? ""
        if !embeddedText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            // Page has extractable text; use it directly (faster, more accurate)
            allText.append("--- Page \(pageIndex + 1) ---")
            allText.append(embeddedText)
            continue
        }

        // No embedded text: render page to image and OCR
        let pageRect = page.bounds(for: .mediaBox)

        // Render at 2x for better OCR accuracy
        let scale: CGFloat = 2.0
        let width = Int(pageRect.width * scale)
        let height = Int(pageRect.height * scale)

        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let bitmapInfo = CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue)

        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: colorSpace,
            bitmapInfo: bitmapInfo.rawValue
        ) else {
            fputs("Warning: Failed to create graphics context for page \(pageIndex + 1)\n", stderr)
            continue
        }

        // White background
        context.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))

        context.scaleBy(x: scale, y: scale)

        // PDFKit page drawing via NSGraphicsContext
        NSGraphicsContext.saveGraphicsState()
        let nsContext = NSGraphicsContext(cgContext: context, flipped: false)
        NSGraphicsContext.current = nsContext
        page.draw(with: .mediaBox, to: context)
        NSGraphicsContext.restoreGraphicsState()

        guard let cgImage = context.makeImage() else {
            fputs("Warning: Failed to render page \(pageIndex + 1) to image\n", stderr)
            continue
        }

        let pageText = performOCR(on: cgImage, languages: languages)

        if !pageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            allText.append("--- Page \(pageIndex + 1) ---")
            allText.append(pageText)
        } else {
            allText.append("--- Page \(pageIndex + 1) ---")
            allText.append("[No text detected]")
        }
    }

    if allText.isEmpty {
        fputs("[Info] No text could be extracted from this PDF\n", stderr)
        return ""
    }

    return allText.joined(separator: "\n")
}

// MARK: - Main

let config = parseArguments()
let (fullPath, isPDF) = validateFile(config.filePath)

let result: String

if isPDF {
    result = ocrPDF(at: fullPath, languages: config.languages, maxPages: config.maxPages)
} else {
    result = ocrImage(at: fullPath, languages: config.languages)
}

if !result.isEmpty {
    print(result)
} else {
    fputs("[Info] No text was extracted from the file\n", stderr)
    exit(0)
}
