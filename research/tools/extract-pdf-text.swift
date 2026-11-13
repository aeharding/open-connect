import Foundation
import PDFKit
// Local, read-only PDF extraction. Output goes beside ignored source snapshots.
guard CommandLine.arguments.count == 2,
      let document = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    fatalError("Supply one local PDF")
}
print("PDF_PAGE_COUNT=\(document.pageCount)")
for index in 0..<document.pageCount {
    print("\n=== PDF PAGE \(index + 1) ===\n")
    print(document.page(at: index)?.string ?? "[no extractable text]")
}
