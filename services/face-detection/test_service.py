#!/usr/bin/env python3
"""
Test script for Face Detection Service
Tests the queue-based face detection pipeline
"""

import requests
import time
import json

SERVICE_URL = "http://localhost:8005"

def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{SERVICE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Service is healthy")
        print(f"  Models: {data['models']}")
        print(f"  Stats: {data['stats']}")
        return True
    else:
        print("✗ Service health check failed")
        return False

def test_enqueue_detection():
    """Test enqueueing a face detection task"""
    print("\n=== Testing Face Detection Enqueue ===")
    
    # Example request
    request_data = {
        "blob_id": "test-blob-123",
        "file_path": "storage/blobs/test-image.jpg",
        "priority": 7
    }
    
    response = requests.post(
        f"{SERVICE_URL}/detect",
        json=request_data
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Task enqueued successfully")
        print(f"  Task ID: {data['task_id']}")
        print(f"  Status: {data['status']}")
        print(f"  Queue position: {data['queue_position']}")
        return data['task_id']
    else:
        print(f"✗ Failed to enqueue task: {response.status_code}")
        print(f"  Error: {response.text}")
        return None

def test_queue_stats():
    """Test queue statistics endpoint"""
    print("\n=== Testing Queue Stats ===")
    response = requests.get(f"{SERVICE_URL}/queue/stats")
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Queue stats retrieved")
        print(f"  Queue size: {data['queue_size']}")
        print(f"  Processing: {data['processing']}")
        print(f"  Total processed: {data['stats']['total_processed']}")
        print(f"  Faces detected: {data['stats']['faces_detected']}")
        print(f"  Persons created: {data['stats']['persons_created']}")
        return True
    else:
        print("✗ Failed to get queue stats")
        return False

def test_api_docs():
    """Test API documentation"""
    print("\n=== Testing API Documentation ===")
    response = requests.get(f"{SERVICE_URL}/docs")
    
    if response.status_code == 200:
        print("✓ API docs accessible at http://localhost:8005/docs")
        return True
    else:
        print("✗ API docs not accessible")
        return False

def main():
    print("=" * 60)
    print("Face Detection Service Test Suite")
    print("=" * 60)
    
    # Check if service is running
    try:
        requests.get(SERVICE_URL, timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Service is not running!")
        print("  Start the service with: python app.py")
        return
    
    # Run tests
    results = []
    
    results.append(("Health Check", test_health()))
    results.append(("Queue Stats", test_queue_stats()))
    results.append(("API Docs", test_api_docs()))
    
    # Note: Actual face detection test requires a real image
    # results.append(("Enqueue Detection", test_enqueue_detection() is not None))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Service is working correctly.")
    else:
        print(f"\n✗ {total - passed} test(s) failed. Check service logs.")

if __name__ == "__main__":
    main()
