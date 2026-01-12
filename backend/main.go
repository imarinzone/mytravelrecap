package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"
)

type PlaceLocation struct {
	Lat      float64  `json:"lat"`
	Lng      float64  `json:"lng"`
	City     *string  `json:"city"`
	Country  *string  `json:"country"`
	PlaceID  string   `json:"place_id"`
}

func getDBConnection() (*sql.DB, error) {
	host := getEnv("DB_HOST", "postgres")
	port := getEnv("DB_PORT", "5432")
	user := getEnv("DB_USER", "travelrecap")
	password := getEnv("DB_PASSWORD", "travelrecap_password")
	dbname := getEnv("DB_NAME", "travelrecap")

	psqlInfo := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)

	db, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		return nil, err
	}

	return db, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next(w, r)
	}
}

func placeLocationsHandler(w http.ResponseWriter, r *http.Request) {
	db, err := getDBConnection()
	if err != nil {
		log.Printf("Error connecting to database: %v", err)
		http.Error(w, "Database connection error", http.StatusInternalServerError)
		return
	}
	defer db.Close()

	rows, err := db.Query(`
		SELECT lat, lng, city, country, place_id
		FROM place_locations
		ORDER BY place_id
	`)
	if err != nil {
		log.Printf("Error querying place_locations: %v", err)
		http.Error(w, "Database query error", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var locations []PlaceLocation
	for rows.Next() {
		var loc PlaceLocation
		err := rows.Scan(&loc.Lat, &loc.Lng, &loc.City, &loc.Country, &loc.PlaceID)
		if err != nil {
			log.Printf("Error scanning row: %v", err)
			continue
		}
		locations = append(locations, loc)
	}

	if err := rows.Err(); err != nil {
		log.Printf("Error iterating rows: %v", err)
		http.Error(w, "Database error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(locations)
}

func main() {
	http.HandleFunc("/api/place-locations", corsMiddleware(placeLocationsHandler))

	port := getEnv("PORT", "8080")
	log.Printf("Server starting on port %s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

