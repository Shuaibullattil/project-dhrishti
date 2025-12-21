from ultralytics import YOLO
import cv2
import numpy as np

model = YOLO('yolov8n.pt')  # Pretrained, person class=0
cap = cv2.VideoCapture(r'vd/street.mp4')

# Define rectangle ROI: x,y,w,h
roi = (100, 100, 400, 900)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    
    results = model(frame, classes=[0], verbose=False)
    detections = results[0].boxes.data.cpu().numpy()  # [x1,y1,x2,y2,conf,class]
    
    roi_count = 0
    for det in detections:
        if int(det[5]) == 0:  # Person class
            # Check center point of the bounding box
            x_center = (det[0] + det[2]) / 2
            y_center = (det[1] + det[3]) / 2
            if (roi[0] < x_center < roi[0]+roi[2]) and (roi[1] < y_center < roi[1]+roi[3]):
                roi_count += 1
    
    density = roi_count / (roi[2] * roi[3]) * 10000  # People per 10k pixels
    print(f"ROI Count: {roi_count}, Density: {density:.2f}")
    
    # Draw ROI and run model viz
    annotated = results[0].plot()
    # Draw ROI on annotated image
    cv2.rectangle(annotated, (roi[0], roi[1]), (roi[0]+roi[2], roi[1]+roi[3]), (0,255,0), 2)
    # Display the count and density on the frame
    text1 = f"Count: {roi_count}"
    text2 = f"Density: {density:.2f}"
    cv2.putText(annotated, text1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(annotated, text2, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.imshow('Crowd Monitor', annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
