"use client";

import { useEffect, useRef, useState } from "react";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

export type MapPoint = { coordinates: [number, number] };
export type FleetMapItem = { fleetId: string; name: string; status: string; location: MapPoint };
export type MapStop = { label: string; location: MapPoint };

type GoogleFleetMapProps = {
  fleets?: FleetMapItem[];
  stops?: MapStop[];
  className?: string;
};

const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
const defaultStops: MapStop[] = [
  { label: "농가", location: { coordinates: [127.017, 36.806] } },
  { label: "서울 구매처", location: { coordinates: [127.028, 37.498] } },
];

function toLatLng(point: MapPoint): google.maps.LatLngLiteral {
  return { lat: point.coordinates[1], lng: point.coordinates[0] };
}

function markerColor(status?: string) {
  if (status === "OUT_OF_SERVICE") return "#9e4f55";
  if (status === "IDLE") return "#bc777a";
  return "#c98a7e";
}

export default function GoogleFleetMap({ fleets = [], stops = defaultStops, className = "" }: GoogleFleetMapProps) {
  const elementRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const overlaysRef = useRef<(google.maps.Marker | google.maps.Polyline)[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | undefined>(
    apiKey ? undefined : "Google Maps API 키가 설정되지 않았습니다.",
  );

  useEffect(() => {
    if (!apiKey) return;
    let active = true;
    async function loadMap() {
      try {
        setOptions({ key: apiKey });
        const { Map: GoogleMap } = await importLibrary("maps");
        await importLibrary("marker");
        if (!active || !elementRef.current) return;
        mapRef.current = new GoogleMap(elementRef.current, {
          center: { lat: 36.75, lng: 127.35 },
          zoom: 8,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
          clickableIcons: false,
        });
        setReady(true);
      } catch {
        if (active) setError("Google Maps를 불러오지 못했습니다. API 키와 도메인 제한을 확인해 주세요.");
      }
    }
    void loadMap();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    overlaysRef.current.forEach((overlay) => overlay.setMap(null));
    overlaysRef.current = [];
    const map = mapRef.current;
    if (!map) return;
    const bounds = new google.maps.LatLngBounds();
    const stopPath = stops.map((stop) => toLatLng(stop.location));
    stopPath.forEach((position) => bounds.extend(position));
    stops.forEach((stop, index) => {
      const marker = new google.maps.Marker({
        map,
        position: toLatLng(stop.location),
        title: stop.label,
        label: { text: index === 0 ? "농" : "구", color: "#fff", fontWeight: "700" },
        icon: { path: google.maps.SymbolPath.CIRCLE, fillColor: index === 0 ? "#a95c61" : "#78565a", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2, scale: 10 },
      });
      overlaysRef.current.push(marker);
    });
    if (stopPath.length > 1) {
      overlaysRef.current.push(new google.maps.Polyline({
        map,
        path: stopPath,
        geodesic: true,
        strokeColor: "#b97679",
        strokeOpacity: 0.9,
        strokeWeight: 4,
      }));
    }
    fleets.forEach((fleet) => {
      const position = toLatLng(fleet.location);
      bounds.extend(position);
      const marker = new google.maps.Marker({
        map,
        position,
        title: `${fleet.name} · ${fleet.status}`,
        label: { text: "●", color: "#fff", fontSize: "12px" },
        icon: { path: google.maps.SymbolPath.CIRCLE, fillColor: markerColor(fleet.status), fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2, scale: 9 },
      });
      overlaysRef.current.push(marker);
    });
    if (!bounds.isEmpty()) map.fitBounds(bounds, 42);
    return () => overlaysRef.current.forEach((overlay) => overlay.setMap(null));
  }, [fleets, ready, stops]);

  return <div className={`google-map-shell ${className}`}><div className="google-map" ref={elementRef} />{error && <div className="google-map-message"><strong>지도를 준비하는 중이야</strong><span>{error}</span></div>}{!error && !ready && <div className="google-map-message"><strong>지도를 불러오는 중...</strong><span>차량 위치와 경로를 연결하고 있어.</span></div>}</div>;
}
