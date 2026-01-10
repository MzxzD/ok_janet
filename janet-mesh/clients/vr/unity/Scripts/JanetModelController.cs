/*
 * JanetModelController.cs - Controls 3D Janet model in VR
 * 
 * Features:
 * - Tone-aware idle animations
 * - Gesture system reflecting Janet's emotional state
 * - Lip-sync driven by TTS audio stream
 * - Eye tracking and attention system (model looks at Operator)
 */

using UnityEngine;
using System.Collections;

public class JanetModelController : MonoBehaviour
{
    [Header("Model References")]
    public GameObject janetModel;
    public SkinnedMeshRenderer faceRenderer;
    public Animator animator;
    
    [Header("Viseme Blendshapes")]
    public int visemeA = 0;
    public int visemeE = 1;
    public int visemeI = 2;
    public int visemeO = 3;
    public int visemeU = 4;
    public int visemeM = 5;
    public int visemeF = 6;
    // Add more viseme indices as needed
    
    [Header("Animation")]
    public string idleAnimName = "Idle";
    public string happyAnimName = "Happy";
    public string thinkingAnimName = "Thinking";
    
    [Header("Audio")]
    public AudioSource audioSource;
    
    private float[] visemeWeights = new float[7]; // Viseme blend weights
    private bool isSpeaking = false;
    private string currentEmotion = "neutral";
    private Transform operatorHead; // Reference to VR headset position
    
    void Start()
    {
        // Initialize viseme weights
        for (int i = 0; i < visemeWeights.Length; i++)
        {
            visemeWeights[i] = 0f;
        }
        
        // Find Operator head (VR camera)
        operatorHead = Camera.main?.transform;
        
        // Start idle animation
        if (animator != null)
        {
            animator.Play(idleAnimName);
        }
    }
    
    void Update()
    {
        // Update viseme blendshapes based on audio
        UpdateVisemes();
        
        // Update eye tracking (look at Operator)
        UpdateEyeTracking();
        
        // Update animation based on emotion
        UpdateAnimation();
    }
    
    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource != null && clip != null)
        {
            audioSource.clip = clip;
            audioSource.Play();
            isSpeaking = true;
            
            // Start lip-sync animation
            StartCoroutine(AnimateLipSync(clip.length));
        }
    }
    
    public void SetEmotion(string emotion)
    {
        // Update emotion state for animation
        currentEmotion = emotion;
        
        // Trigger appropriate animation
        if (animator != null)
        {
            switch (emotion.ToLower())
            {
                case "happy":
                case "joyful":
                    animator.Play(happyAnimName);
                    break;
                case "thinking":
                case "curious":
                    animator.Play(thinkingAnimName);
                    break;
                default:
                    animator.Play(idleAnimName);
                    break;
            }
        }
    }
    
    private void UpdateVisemes()
    {
        if (faceRenderer == null || !isSpeaking)
        {
            // Reset visemes when not speaking
            for (int i = 0; i < visemeWeights.Length; i++)
            {
                visemeWeights[i] = 0f;
            }
            return;
        }
        
        // Update viseme weights based on audio analysis
        // This is a placeholder - in production, use audio analysis to detect visemes
        // For now, animate based on audio amplitude
        float amplitude = audioSource.isPlaying ? audioSource.volume : 0f;
        
        // Simple viseme animation (replace with actual audio analysis)
        visemeWeights[0] = Mathf.Sin(Time.time * 10f) * amplitude * 0.5f; // A
        visemeWeights[1] = Mathf.Sin(Time.time * 12f) * amplitude * 0.3f; // E
        // Add more viseme calculations...
        
        // Apply to blendshapes
        if (faceRenderer != null && faceRenderer.sharedMesh != null)
        {
            faceRenderer.SetBlendShapeWeight(visemeA, visemeWeights[0] * 100f);
            faceRenderer.SetBlendShapeWeight(visemeE, visemeWeights[1] * 100f);
            // Apply other visemes...
        }
    }
    
    private void UpdateEyeTracking()
    {
        if (operatorHead == null || janetModel == null)
            return;
        
        // Make Janet look at Operator
        Vector3 directionToOperator = operatorHead.position - janetModel.transform.position;
        directionToOperator.y = 0; // Keep head level
        
        // Rotate head slightly toward Operator (if head bone exists)
        // This is simplified - in production, use IK or bone rotation
        Quaternion targetRotation = Quaternion.LookRotation(directionToOperator);
        janetModel.transform.rotation = Quaternion.Slerp(
            janetModel.transform.rotation,
            targetRotation,
            Time.deltaTime * 2f
        );
    }
    
    private void UpdateAnimation()
    {
        // Animation is updated via SetEmotion() method
        // This method can be extended for more dynamic animation
    }
    
    private IEnumerator AnimateLipSync(float duration)
    {
        isSpeaking = true;
        yield return new WaitForSeconds(duration);
        isSpeaking = false;
    }
}
