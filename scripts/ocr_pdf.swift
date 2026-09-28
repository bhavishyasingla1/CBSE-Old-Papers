import Foundation
import PDFKit
import Vision

guard CommandLine.arguments.count >= 3 else {
    print("Usage: swift ocr_pdf.swift <pdf_path> <output_json_path>")
    exit(1)
}

let pdfPath = CommandLine.arguments[1]
let outPath = CommandLine.arguments[2]

let pdfURL = URL(fileURLWithPath: pdfPath)
guard let doc = PDFDocument(url: pdfURL) else {
    print("Could not open PDF: \(pdfPath)")
    exit(1)
}

struct PageResult: Codable {
    let page: Int
    let text: String
}

var results: [PageResult] = []

for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let nativeText = page.string ?? ""
    if nativeText.trimmingCharacters(in: .whitespacesAndNewlines).count > 50 {
        results.append(PageResult(page: i + 1, text: nativeText))
        continue
    }
    
    // Fallback to Vision OCR
    let bounds = page.bounds(for: .mediaBox)
    // Scale up for high OCR accuracy
    let targetSize = CGSize(width: max(bounds.width * 2.0, 1400), height: max(bounds.height * 2.0, 1800))
    let image = page.thumbnail(of: targetSize, for: .mediaBox)
    
    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let cg = rep.cgImage else {
        results.append(PageResult(page: i + 1, text: ""))
        continue
    }
    
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([req])
    
    let lines = (req.results as? [VNRecognizedTextObservation] ?? []).compactMap { $0.topCandidates(1).first?.string }
    results.append(PageResult(page: i + 1, text: lines.joined(separator: "\n")))
}

let encoder = JSONEncoder()
encoder.outputFormatting = .prettyPrinted
if let data = try? encoder.encode(results) {
    try? data.write(to: URL(fileURLWithPath: outPath))
    print("Successfully processed \(results.count) pages -> \(outPath)")
}
