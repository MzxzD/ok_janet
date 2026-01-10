import SwiftUI
import PDFKit
import CoreText
import UIKit

class PDFExporter {
    static func exportConversation(messages: [Message]) -> URL? {
        let pdfMetaData = [
            kCGPDFContextCreator: "Janet Mesh Client",
            kCGPDFContextAuthor: "Janet Conversation",
            kCGPDFContextTitle: "Janet Conversation Export"
        ]
        let format = UIGraphicsPDFRendererFormat()
        format.documentInfo = pdfMetaData as [String: Any]
        
        let pageWidth = 8.5 * 72.0
        let pageHeight = 11 * 72.0
        let pageRect = CGRect(x: 0, y: 0, width: pageWidth, height: pageHeight)
        
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect, format: format)
        
        let data = renderer.pdfData { (context: UIGraphicsPDFRendererContext) in
            context.beginPage()
            
            let cgContext = context.cgContext
            var yPosition: CGFloat = 60
            
            // Title
            let titleAttributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 24),
                .foregroundColor: UIColor.black  // Use black for PDF
            ]
            let title = "Janet Conversation"
            title.draw(at: CGPoint(x: 60, y: yPosition), withAttributes: titleAttributes)
            yPosition += 40
            
            // Date
            let dateFormatter = DateFormatter()
            dateFormatter.dateStyle = .medium
            dateFormatter.timeStyle = .short
            let dateAttributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 12),
                .foregroundColor: UIColor.gray  // Use gray for PDF
            ]
            let dateString = "Exported: \(dateFormatter.string(from: Date()))"
            dateString.draw(at: CGPoint(x: 60, y: yPosition), withAttributes: dateAttributes)
            yPosition += 30
            
            // Messages
            let messageAttributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 14),
                .foregroundColor: UIColor.black  // Use black for PDF (label color might not render correctly)
            ]
            
            let userAttributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 14),
                .foregroundColor: UIColor.systemBlue
            ]
            
            let timestampAttributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 10),
                .foregroundColor: UIColor.gray  // Use gray for PDF
            ]
            
            for message in messages {
                // Check if we need a new page
                if yPosition > pageHeight - 100 {
                    context.beginPage()
                    yPosition = 60
                }
                
                // Timestamp
                let timeString = dateFormatter.string(from: message.timestamp)
                timeString.draw(at: CGPoint(x: 60, y: yPosition), withAttributes: timestampAttributes)
                yPosition += 18
                
                // Sender label
                let senderLabel = message.isFromUser ? "You" : "Janet"
                senderLabel.draw(at: CGPoint(x: 60, y: yPosition), withAttributes: userAttributes)
                yPosition += 20
                
                // Message text (with word wrapping)
                // Ensure we have text to render
                let messageText = message.text.isEmpty ? "(empty message)" : message.text
                let textWidth = max(pageWidth - 120, 100)  // Ensure minimum width to prevent NaN
                let maxHeight = max(pageHeight - yPosition - 40, 100)  // Ensure minimum height
                
                // Create attributed string with proper attributes
                let attributedText = NSAttributedString(string: messageText, attributes: messageAttributes)
                
                // Calculate text size first
                let textSize = attributedText.boundingRect(
                    with: CGSize(width: textWidth, height: .greatestFiniteMagnitude),
                    options: [.usesLineFragmentOrigin, .usesFontLeading],
                    context: nil
                )
                
                // Validate text size
                let validHeight = textSize.height.isFinite && !textSize.height.isNaN && textSize.height > 0 
                    ? ceil(textSize.height) 
                    : 20.0  // Fallback height
                
                // Create text frame using CoreText for reliable PDF rendering
                let textRect = CGRect(x: 60, y: yPosition, width: textWidth, height: max(validHeight, 20))
                
                // Save graphics state
                cgContext.saveGState()
                
                // Set text matrix (PDF uses flipped coordinate system)
                cgContext.textMatrix = CGAffineTransform.identity
                cgContext.translateBy(x: 0, y: pageHeight)
                cgContext.scaleBy(x: 1.0, y: -1.0)
                
                // Create path for text
                let path = CGMutablePath()
                let flippedRect = CGRect(
                    x: textRect.origin.x,
                    y: pageHeight - textRect.origin.y - textRect.height,
                    width: textRect.width,
                    height: textRect.height
                )
                path.addRect(flippedRect)
                
                // Create framesetter and frame
                let framesetter = CTFramesetterCreateWithAttributedString(attributedText)
                let frame = CTFramesetterCreateFrame(framesetter, CFRangeMake(0, 0), path, nil)
                
                // Draw the frame
                CTFrameDraw(frame, cgContext)
                
                // Restore graphics state
                cgContext.restoreGState()
                
                // Update y position based on actual text height (with validation)
                let textHeight = max(validHeight, 20) // Minimum height for empty messages
                yPosition += textHeight + 30
                
                // Safety check to prevent infinite loops or invalid positions
                if !yPosition.isFinite || yPosition.isNaN || yPosition > pageHeight * 10 {
                    print("⚠️ Invalid yPosition detected: \(yPosition), breaking PDF generation")
                    break
                }
            }
        }
        
        // Save to temporary file
        let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("janet-conversation-\(UUID().uuidString).pdf")
        do {
            try data.write(to: tempURL)
            return tempURL
        } catch {
            print("Error saving PDF: \(error)")
            return nil
        }
    }
}
