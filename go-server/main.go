package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

type ProcessRequest struct {
	Text string `json:"text"`
}

type ProcessResponse struct {
	Result string `json:"result"`
}

func main() {
	pythonServiceURL := getEnv("PYTHON_SERVICE_URL", "http://python-worker:5000/process")

	mux := http.NewServeMux()
	mux.HandleFunc("/process", func(w http.ResponseWriter, r *http.Request) {
		handleProcess(w, r, pythonServiceURL)
	})
	mux.HandleFunc("/health", healthHandler)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      loggingMiddleware(mux),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
		IdleTimeout:  30 * time.Second,
	}

	log.Println("Go server started on :8080")
	log.Println("Python service URL:", pythonServiceURL)

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func handleProcess(w http.ResponseWriter, r *http.Request, pythonServiceURL string) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{
			"error": "method not allowed",
		})
		return
	}

	var req ProcessRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "invalid json",
		})
		return
	}

	if req.Text == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "text is required",
		})
		return
	}

	payload, err := json.Marshal(req)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{
			"error": "failed to encode request",
		})
		return
	}

	client := &http.Client{
		Timeout: 3 * time.Second,
	}

	pythonReq, err := http.NewRequest(http.MethodPost, pythonServiceURL, bytes.NewBuffer(payload))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{
			"error": "failed to create request to python service",
		})
		return
	}
	pythonReq.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(pythonReq)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": fmt.Sprintf("python service unavailable: %v", err),
		})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": "failed to read python service response",
		})
		return
	}

	if resp.StatusCode != http.StatusOK {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		w.Write(body)
		return
	}

	var pythonResp ProcessResponse
	if err := json.Unmarshal(body, &pythonResp); err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": "invalid response from python service",
		})
		return
	}

	writeJSON(w, http.StatusOK, pythonResp)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status": "ok",
	})
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		log.Printf("started %s %s", r.Method, r.URL.Path)
		next.ServeHTTP(w, r)
		log.Printf("completed %s %s in %v", r.Method, r.URL.Path, time.Since(start))
	})
}

func getEnv(key, fallback string) string {
	val := os.Getenv(key)
	if val == "" {
		return fallback
	}
	return val
}
