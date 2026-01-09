import SwiftUI

struct ChatView: View {
    @ObservedObject var webSocketManager: WebSocketManager
    @State private var inputText: String = ""
    @FocusState private var isInputFocused: Bool
    
    var body: some View {
        VStack(spacing: 0) {
            // Messages list
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        if webSocketManager.messages.isEmpty {
                            VStack(spacing: 16) {
                                Image(systemName: "message.circle.fill")
                                    .font(.system(size: 60))
                                    .foregroundColor(.gray.opacity(0.5))
                                Text("Start chatting with Janet")
                                    .font(.headline)
                                    .foregroundColor(.gray)
                                Text("Type a message below to begin")
                                    .font(.subheadline)
                                    .foregroundColor(.gray.opacity(0.7))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, 100)
                            .onAppear {
                                print("💬 Empty state visible")
                            }
                        } else {
                            ForEach(webSocketManager.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                            
                            // Typing indicator
                            if webSocketManager.isWaitingForResponse {
                                HStack {
                                    TypingIndicator()
                                    Spacer()
                                }
                                .padding(.horizontal)
                            }
                        }
                    }
                    .padding()
                }
                .onAppear {
                    print("💬 ChatView appeared, messages: \(webSocketManager.messages.count), connected: \(webSocketManager.isConnected)")
                }
                .onChange(of: webSocketManager.messages.count) { newCount in
                    print("💬 Message count changed to: \(newCount)")
                    if let lastMessage = webSocketManager.messages.last {
                        withAnimation {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
                .onChange(of: webSocketManager.isWaitingForResponse) { _ in
                    if webSocketManager.isWaitingForResponse {
                        withAnimation {
                            if let lastMessage = webSocketManager.messages.last {
                                proxy.scrollTo(lastMessage.id, anchor: .bottom)
                            }
                        }
                    }
                }
            }
            
            Divider()
            
            // Input area
            HStack(spacing: 12) {
                if #available(iOS 16.0, *) {
                    TextField("Type a message...", text: $inputText, axis: .vertical)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(20)
                        .lineLimit(1...5)
                        .focused($isInputFocused)
                        .disabled(!webSocketManager.isConnected || webSocketManager.isWaitingForResponse)
                        .onSubmit {
                            sendMessage()
                        }
                } else {
                    TextField("Type a message...", text: $inputText)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(20)
                        .lineLimit(5)
                        .focused($isInputFocused)
                        .disabled(!webSocketManager.isConnected || webSocketManager.isWaitingForResponse)
                        .onSubmit {
                            sendMessage()
                        }
                }
                
                Button(action: sendMessage) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(canSend ? .blue : .gray)
                }
                .disabled(!canSend)
            }
            .padding()
            .background(Color(.systemBackground))
            .onAppear {
                print("💬 Input area visible, canSend: \(canSend), connected: \(webSocketManager.isConnected)")
            }
        }
        .background(Color(.systemGroupedBackground))
        .onAppear {
            print("💬 ChatView body rendered")
        }
    }
    
    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        webSocketManager.isConnected &&
        !webSocketManager.isWaitingForResponse
    }
    
    private func sendMessage() {
        guard canSend else { return }
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        webSocketManager.sendText(text)
        inputText = ""
        isInputFocused = false
    }
}

struct MessageBubble: View {
    let message: Message
    
    var body: some View {
        HStack {
            if message.isFromUser {
                Spacer(minLength: 50)
            }
            
            VStack(alignment: message.isFromUser ? .trailing : .leading, spacing: 4) {
                Text(message.text)
                    .font(.body)
                    .foregroundColor(message.isFromUser ? .white : .primary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(
                        message.isFromUser ?
                        Color.blue : Color(.systemGray5)
                    )
                    .cornerRadius(18)
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.gray)
                    .padding(.horizontal, 4)
            }
            
            if !message.isFromUser {
                Spacer(minLength: 50)
            }
        }
    }
}

struct TypingIndicator: View {
    @State private var animationPhase = 0
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.gray)
                    .frame(width: 8, height: 8)
                    .scaleEffect(animationPhase == index ? 1.2 : 0.8)
                    .animation(
                        Animation.easeInOut(duration: 0.6)
                            .repeatForever()
                            .delay(Double(index) * 0.2),
                        value: animationPhase
                    )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(.systemGray5))
        .cornerRadius(18)
        .onAppear {
            animationPhase = 0
            withAnimation {
                animationPhase = 1
            }
        }
    }
}
