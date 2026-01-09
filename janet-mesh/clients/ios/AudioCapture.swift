import Foundation
import AVFoundation
import Combine

/// Captures audio from microphone
class AudioCapture: NSObject, ObservableObject {
    @Published var isRecording = false
    @Published var audioLevel: Float = 0.0
    
    private var audioEngine: AVAudioEngine?
    private var inputNode: AVAudioInputNode?
    private var audioFormat: AVAudioFormat?
    
    func startRecording() throws {
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .default)
        try audioSession.setActive(true)
        
        audioEngine = AVAudioEngine()
        guard let audioEngine = audioEngine else { return }
        
        inputNode = audioEngine.inputNode
        audioFormat = inputNode?.outputFormat(forBus: 0)
        
        // Install tap to capture audio
        let bufferSize: AVAudioFrameCount = 4096
        inputNode?.installTap(onBus: 0, bufferSize: bufferSize, format: audioFormat) { [weak self] buffer, time in
            self?.processAudioBuffer(buffer)
        }
        
        try audioEngine.start()
        isRecording = true
    }
    
    func stopRecording() {
        inputNode?.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
        inputNode = nil
        audioFormat = nil
        isRecording = false
        
        let audioSession = AVAudioSession.sharedInstance()
        try? audioSession.setActive(false)
    }
    
    private func processAudioBuffer(_ buffer: AVAudioPCMBuffer) {
        // Calculate audio level
        guard let channelData = buffer.floatChannelData else { return }
        let channelDataValue = channelData.pointee
        let channelDataValueArray = stride(from: 0, to: Int(buffer.frameLength), by: buffer.stride)
            .map { channelDataValue[$0] }
        
        let rms = sqrt(channelDataValueArray.map { $0 * $0 }.reduce(0, +) / Float(buffer.frameLength))
        let avgPower = 20 * log10(rms)
        let normalizedLevel = max(0.0, (avgPower + 60) / 60) // Normalize to 0-1
        
        DispatchQueue.main.async {
            self.audioLevel = normalizedLevel
        }
    }
    
    func getAudioData(from buffer: AVAudioPCMBuffer) -> Data? {
        guard let audioFormat = audioFormat else { return nil }
        
        // Convert to WAV format
        let sampleRate = Int(audioFormat.sampleRate)
        let channels = Int(audioFormat.channelCount)
        let bitsPerSample = 16
        
        var wavData = Data()
        
        // WAV header
        let headerSize = 44
        let dataSize = Int(buffer.frameLength) * channels * (bitsPerSample / 8)
        let fileSize = headerSize + dataSize
        
        // RIFF header
        wavData.append("RIFF".data(using: .ascii)!)
        wavData.append(contentsOf: withUnsafeBytes(of: UInt32(fileSize).littleEndian) { Data($0) })
        wavData.append("WAVE".data(using: .ascii)!)
        
        // fmt chunk
        wavData.append("fmt ".data(using: .ascii)!)
        wavData.append(contentsOf: withUnsafeBytes(of: UInt32(16).littleEndian) { Data($0) }) // fmt chunk size
        wavData.append(contentsOf: withUnsafeBytes(of: UInt16(1).littleEndian) { Data($0) }) // audio format (PCM)
        wavData.append(contentsOf: withUnsafeBytes(of: UInt16(channels).littleEndian) { Data($0) })
        wavData.append(contentsOf: withUnsafeBytes(of: UInt32(sampleRate).littleEndian) { Data($0) })
        wavData.append(contentsOf: withUnsafeBytes(of: UInt32(sampleRate * channels * (bitsPerSample / 8)).littleEndian) { Data($0) })
        wavData.append(contentsOf: withUnsafeBytes(of: UInt16(channels * (bitsPerSample / 8)).littleEndian) { Data($0) })
        wavData.append(contentsOf: withUnsafeBytes(of: UInt16(bitsPerSample).littleEndian) { Data($0) })
        
        // data chunk
        wavData.append("data".data(using: .ascii)!)
        wavData.append(contentsOf: withUnsafeBytes(of: UInt32(dataSize).littleEndian) { Data($0) })
        
        // Audio data
        guard let channelData = buffer.floatChannelData else { return nil }
        for i in 0..<Int(buffer.frameLength) {
            let sample = channelData.pointee[i]
            let intSample = Int16(max(-32768, min(32767, sample * 32768.0)))
            wavData.append(contentsOf: withUnsafeBytes(of: intSample.littleEndian) { Data($0) })
        }
        
        return wavData
    }
}
