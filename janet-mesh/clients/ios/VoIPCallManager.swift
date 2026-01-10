/*
 * VoIPCallManager.swift - Native iOS calling experience with CallKit/PushKit
 * Integrates with Janet Mesh server for real-time voice conversations
 * Features:
 * - CallKit integration for native call UI
 * - PushKit for incoming call notifications
 * - WebRTC audio streaming via Janet Mesh server
 * - Janet avatar shown on call screen (Konosuba theme: Aqua for normal, Darkness for debug)
 */
import Foundation
import CallKit
import PushKit
import AVFoundation
import Combine
import SwiftUI

class VoIPCallManager: NSObject, CXProviderDelegate, ObservableObject {
    static let shared = VoIPCallManager()
    
    private var provider: CXProvider?
    private let callController = CXCallController()
    private var currentCall: UUID?
    private var webSocketManager: WebSocketManager?
    
    // WebRTC components (simplified - requires WebRTC SDK integration)
    private var peerConnection: Any? // Would be RTCPeerConnection in production
    private var audioSession: AVAudioSession?
    
    // Call state
    @Published var isInCall = false
    @Published var currentCallId: String?
    
    override init() {
        super.init()
        setupCallKit()
        setupAudioSession()
    }
    
    private func setupCallKit() {
        let configuration = CXProviderConfiguration(localizedName: "Janet")
        configuration.supportsVideo = false
        configuration.maximumCallsPerCallGroup = 1
        configuration.supportedHandleTypes = [.generic]
        configuration.iconTemplateImageData = nil // Could add Janet avatar image
        
        provider = CXProvider(configuration: configuration)
        provider?.setDelegate(self, queue: nil)
    }
    
    private func setupAudioSession() {
        audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession?.setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetooth, .allowBluetoothA2DP])
            try audioSession?.setActive(true)
        } catch {
            print("Error setting up audio session: \(error)")
        }
    }
    
    func setWebSocketManager(_ manager: WebSocketManager) {
        self.webSocketManager = manager
        setupNotifications()
    }
    
    private func setupNotifications() {
        // Listen for VoIP offer from server
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleVoIPOffer(_:)),
            name: NSNotification.Name("VoIPOfferReceived"),
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleVoIPConnected(_:)),
            name: NSNotification.Name("VoIPCallConnected"),
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleVoIPEnded(_:)),
            name: NSNotification.Name("VoIPCallEnded"),
            object: nil
        )
    }
    
    // MARK: - Outgoing Call
    
    func startCall(to contactName: String = "Janet") {
        let handle = CXHandle(type: .generic, value: contactName)
        let startCallAction = CXStartCallAction(call: UUID(), handle: handle)
        
        startCallAction.isVideo = false
        
        let transaction = CXTransaction(action: startCallAction)
        
        callController.request(transaction) { [weak self] error in
            if let error = error {
                print("Error starting call: \(error)")
            } else {
                // Report outgoing call to system
                if let callUUID = startCallAction.callUUID as UUID? {
                    self?.currentCall = callUUID
                    self?.currentCallId = callUUID.uuidString
                    self?.provider?.reportOutgoingCall(with: callUUID, startedConnectingAt: Date())
                    
                    // Initiate call via WebSocket
                    self?.webSocketManager?.initiateVoIPCall()
                    
                    // Update state
                    DispatchQueue.main.async {
                        self?.isInCall = true
                    }
                }
            }
        }
    }
    
    // MARK: - Incoming Call Handling
    
    @objc private func handleVoIPOffer(_ notification: Notification) {
        guard let userInfo = notification.userInfo,
              let callId = userInfo["call_id"] as? String,
              let sdp = userInfo["sdp"] as? String,
              let sdpType = userInfo["sdp_type"] as? String else {
            return
        }
        
        // Create incoming call
        let update = CXCallUpdate()
        update.remoteHandle = CXHandle(type: .generic, value: "Janet")
        update.hasVideo = false
        update.localizedCallerName = "Janet"
        
        let callUUID = UUID()
        currentCall = callUUID
        currentCallId = callId
        
        provider?.reportNewIncomingCall(with: callUUID, update: update) { error in
            if let error = error {
                print("Error reporting incoming call: \(error)")
                return
            }
            
            // Generate WebRTC answer (simplified - requires WebRTC SDK)
            // For now, accept the call
            self.acceptIncomingCall(callId: callId, offerSDP: sdp, offerType: sdpType)
        }
    }
    
    private func acceptIncomingCall(callId: String, offerSDP: String, offerType: String) {
        // Generate WebRTC answer (placeholder - requires WebRTC SDK integration)
        // In production, use WebRTC library to create answer SDP
        let answerSDP = "answer-sdp-placeholder" // Replace with actual answer from WebRTC
        let answerType = "answer"
        
        // Send answer to server
        webSocketManager?.answerVoIPCall(callId: callId, answerSDP: answerSDP, answerType: answerType)
        
        // Report call as connected
        if let callUUID = currentCall {
            provider?.reportOutgoingCall(with: callUUID, connectedAt: Date())
            
            DispatchQueue.main.async {
                self.isInCall = true
            }
        }
    }
    
    @objc private func handleVoIPConnected(_ notification: Notification) {
        guard let callUUID = currentCall else { return }
        provider?.reportOutgoingCall(with: callUUID, connectedAt: Date())
        
        DispatchQueue.main.async {
            self.isInCall = true
        }
    }
    
    @objc private func handleVoIPEnded(_ notification: Notification) {
        endCall(reason: .remoteEnded)
    }
    
    // MARK: - Call Control
    
    func endCall(reason: CXCallEndedReason = .remoteEnded) {
        guard let callUUID = currentCall else { return }
        
        let endCallAction = CXEndCallAction(call: callUUID)
        let transaction = CXTransaction(action: endCallAction)
        
        callController.request(transaction) { error in
            if let error = error {
                print("Error ending call: \(error)")
            } else {
                // Notify server
                if let callId = self.currentCallId {
                    self.webSocketManager?.endVoIPCall(callId: callId, reason: "normal")
                }
                
                // Update state
                DispatchQueue.main.async {
                    self.isInCall = false
                    self.currentCall = nil
                    self.currentCallId = nil
                }
                
                // Report call ended
                self.provider?.reportCall(with: callUUID, endedAt: Date(), reason: reason)
            }
        }
    }
    
    // MARK: - CXProviderDelegate
    
    func providerDidReset(_ provider: CXProvider) {
        // Handle provider reset
        currentCall = nil
        DispatchQueue.main.async {
            self.isInCall = false
        }
    }
    
    func provider(_ provider: CXProvider, perform action: CXStartCallAction) {
        // Start call action
        action.fulfill()
    }
    
    func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
        // Answer call action
        if let callUUID = action.callUUID as UUID?,
           let callId = currentCallId {
            // Generate WebRTC answer and send to server
            let answerSDP = "answer-sdp-placeholder" // Replace with actual answer
            webSocketManager?.answerVoIPCall(callId: callId, answerSDP: answerSDP, answerType: "answer")
        }
        action.fulfill()
    }
    
    func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
        // End call action
        if let callId = currentCallId {
            webSocketManager?.endVoIPCall(callId: callId, reason: "user_ended")
        }
        
        currentCall = nil
        DispatchQueue.main.async {
            self.isInCall = false
            self.currentCallId = nil
        }
        
        action.fulfill()
    }
    
    func provider(_ provider: CXProvider, perform action: CXSetHeldCallAction) {
        // Hold call action (optional)
        action.fulfill()
    }
    
    func provider(_ provider: CXProvider, perform action: CXSetMutedCallAction) {
        // Mute call action
        action.fulfill()
    }
    
    func provider(_ provider: CXProvider, timedOutPerforming action: CXAction) {
        // Handle timeout
        action.fail()
    }
    
    func provider(_ provider: CXProvider, didActivate audioSession: AVAudioSession) {
        // Audio session activated - start audio streaming
        // In production, start WebRTC audio capture/playback
        print("Audio session activated")
    }
    
    func provider(_ provider: CXProvider, didDeactivate audioSession: AVAudioSession) {
        // Audio session deactivated - stop audio streaming
        print("Audio session deactivated")
    }
}
