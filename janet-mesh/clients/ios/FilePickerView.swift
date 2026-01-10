/*
 * FilePickerView.swift - File and image picker for iOS client
 * Supports selecting files from Files app or capturing images from camera
 */
import SwiftUI
import UIKit
import UniformTypeIdentifiers
import PhotosUI

struct FilePickerView: UIViewControllerRepresentable {
    let onFileSelected: (URL, Data, String, String) -> Void
    
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        picker.sourceType = .photoLibrary
        picker.allowsEditing = false
        picker.mediaTypes = ["public.image", "public.movie"]
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: FilePickerView
        
        init(_ parent: FilePickerView) {
            self.parent = parent
        }
        
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            picker.dismiss(animated: true)
            
            if let image = info[.originalImage] as? UIImage {
                // Convert UIImage to Data (JPEG)
                if let imageData = image.jpegData(compressionQuality: 0.8) {
                    let fileName = "image_\(Date().timeIntervalSince1970).jpg"
                    let fileURL = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent(fileName)
                    
                    // Save temporarily and call callback
                    do {
                        try imageData.write(to: fileURL)
                        parent.onFileSelected(fileURL, imageData, fileName, "image/jpeg")
                    } catch {
                        print("Error saving image: \(error)")
                    }
                }
            }
        }
        
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
        }
    }
}

// Document picker for PDF, text files, etc.
struct DocumentPickerView: UIViewControllerRepresentable {
    let onFileSelected: (URL, Data, String, String) -> Void
    
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [
            UTType.image,
            UTType.pdf,
            UTType.plainText,
            UTType.text,
            UTType.data
        ], asCopy: true)
        picker.delegate = context.coordinator
        picker.allowsMultipleSelection = false
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let parent: DocumentPickerView
        
        init(_ parent: DocumentPickerView) {
            self.parent = parent
        }
        
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard let url = urls.first else { return }
            
            // Access file with security-scoped resource
            guard url.startAccessingSecurityScopedResource() else {
                print("Failed to access security-scoped resource")
                return
            }
            defer { url.stopAccessingSecurityScopedResource() }
            
            // Read file data
            do {
                let fileData = try Data(contentsOf: url)
                let fileName = url.lastPathComponent
                let fileType = url.pathExtension.lowercased()
                
                // Determine MIME type
                var mimeType = "application/octet-stream"
                if fileType == "jpg" || fileType == "jpeg" {
                    mimeType = "image/jpeg"
                } else if fileType == "png" {
                    mimeType = "image/png"
                } else if fileType == "pdf" {
                    mimeType = "application/pdf"
                } else if fileType == "txt" || fileType == "md" {
                    mimeType = "text/plain"
                }
                
                parent.onFileSelected(url, fileData, fileName, mimeType)
            } catch {
                print("Error reading file: \(error)")
            }
        }
        
        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            controller.dismiss(animated: true)
        }
    }
}

// Combined file picker with options
struct CombinedFilePickerView: View {
    @Environment(\.dismiss) var dismiss
    let onFileSelected: (URL, Data, String, String) -> Void
    @State private var showImagePicker = false
    @State private var showDocumentPicker = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Button(action: {
                    showImagePicker = true
                }) {
                    HStack {
                        Image(systemName: "photo")
                            .font(.system(size: 24))
                        Text("Choose Photo")
                            .font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .foregroundColor(.blue)
                    .cornerRadius(12)
                }
                .sheet(isPresented: $showImagePicker) {
                    FilePickerView(onFileSelected: { url, data, fileName, fileType in
                        onFileSelected(url, data, fileName, fileType)
                        dismiss()
                    })
                }
                
                Button(action: {
                    showDocumentPicker = true
                }) {
                    HStack {
                        Image(systemName: "doc")
                            .font(.system(size: 24))
                        Text("Choose Document")
                            .font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .foregroundColor(.blue)
                    .cornerRadius(12)
                }
                .sheet(isPresented: $showDocumentPicker) {
                    DocumentPickerView(onFileSelected: { url, data, fileName, fileType in
                        onFileSelected(url, data, fileName, fileType)
                        dismiss()
                    })
                }
            }
            .padding()
            .navigationTitle("Upload File")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
}
