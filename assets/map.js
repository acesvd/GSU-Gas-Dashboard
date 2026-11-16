
/* ==================================================
   GSU GAS STATION DASHBOARD
   Interactive Google Maps Component

   Responsibilities:
   - Load Google Maps
   - Initialize and preserve the map
   - Manage station markers
   - Update radius circle continuously
   - Identify cheapest eligible stations
   - Display station information
   - Communicate selected radius to Streamlit
   ================================================== */


// Streamlit Components V2 entry point
export default function (component) {

    const {
        data,
        parentElement,
        setStateValue
    } = component;


    // ==================================================
    // 1. CONSTANTS
    // ==================================================

    const MILES_TO_METERS = 1609.344;

    const MIN_RADIUS = 0.50;
    const MAX_RADIUS = 3.00;

    const COLORS = {
        cheapest: "#16a34a",
        eligible: "#2563eb",
        unavailable: "#94a3b8",
        campus: "#d97706",
        radius: "#2563eb"
    };


    // ==================================================
    // 2. PRESERVE MAP STATE
    // ==================================================

    // This state belongs to the component's DOM element.
    // It remains available across Streamlit reruns as long
    // as the component stays mounted with the same key.

    const state = parentElement._gsuMapState ??= {

        map: null,

        circle: null,

        infoWindow: null,

        markers: [],

        stationSignature: null,

        initializing: null,

        AdvancedMarkerElement: null,

        PinElement: null,

        latestData: null,

        activeStationId: null

    };

    // Always store the newest data from Python.
    state.latestData = data;


    // ==================================================
    // 3. GET HTML ELEMENTS
    // ==================================================

    const mapContainer =
        parentElement.querySelector("#gsu-map");

    const slider =
        parentElement.querySelector("#gsu-radius-slider");

    const radiusLabel =
        parentElement.querySelector("#gsu-radius-value");

    const countLabel =
        parentElement.querySelector("#gsu-visible-count");

    const bestLabel =
        parentElement.querySelector("#gsu-best-station");


    // ==================================================
    // 4. RADIUS HELPERS
    // ==================================================

    function clampRadius(value) {

        const numericValue = Number(value);

        if (!Number.isFinite(numericValue)) {
            return 2.00;
        }

        return Math.min(
            MAX_RADIUS,
            Math.max(MIN_RADIUS, numericValue)
        );

    }


    function updateSliderAppearance(radius) {

        // Display radius with two decimal places.
        radiusLabel.textContent =
            radius.toFixed(2) + " miles";

        // Update the colored progress portion.
        const progress = (
            (radius - MIN_RADIUS) /
            (MAX_RADIUS - MIN_RADIUS)
        ) * 100;

        slider.style.setProperty(
            "--gsu-slider-progress",
            progress + "%"
        );

    }


    // ==================================================
    // 5. IDENTIFY VISIBLE AND CHEAPEST STATIONS
    // ==================================================

    function updateMapRadius(radius) {

        radius = clampRadius(radius);

        updateSliderAppearance(radius);

        // Map may still be loading.
        if (!state.map || !state.circle) {
            return;
        }


        // ----------------------------------------------
        // UPDATE CIRCLE
        // ----------------------------------------------

        // This modifies the existing circle instead
        // of recreating the entire Google Map.

        state.circle.setRadius(
            radius * MILES_TO_METERS
        );


        // ----------------------------------------------
        // DETERMINE VISIBLE STATIONS
        // ----------------------------------------------

        const visibleStations = state.markers.filter(
            item => item.station.distance <= radius
        );


        // ----------------------------------------------
        // IDENTIFY ELIGIBLE PRICES
        // ----------------------------------------------

        const eligibleStations = visibleStations
            .filter(item =>
                item.station.eligible &&
                Number.isFinite(item.station.price)
            )
            .sort((a, b) => {

                // Lowest price first.
                const priceDifference =
                    a.station.price - b.station.price;

                if (priceDifference !== 0) {
                    return priceDifference;
                }

                // For equal prices, prefer closer stations.
                return (
                    a.station.distance -
                    b.station.distance
                );

            });


        const bestStation = eligibleStations.length > 0
            ? eligibleStations[0].station
            : null;

        const lowestPrice = bestStation
            ? bestStation.price
            : null;


        // ----------------------------------------------
        // UPDATE MARKER VISIBILITY AND COLORS
        // ----------------------------------------------

        for (const item of state.markers) {

            const station = item.station;

            const withinRadius =
                station.distance <= radius;

            // Show or hide marker without recreating it.
            item.marker.map = withinRadius
                ? state.map
                : null;


            // Determine whether this station is tied
            // for the lowest eligible price.
            const isCheapest = (
                withinRadius &&
                station.eligible &&
                lowestPrice !== null &&
                Number.isFinite(station.price) &&
                Math.abs(
                    station.price - lowestPrice
                ) < 0.000001
            );


            // Assign marker color.
            let markerColor = COLORS.unavailable;

            if (station.eligible) {
                markerColor = COLORS.eligible;
            }

            if (isCheapest) {
                markerColor = COLORS.cheapest;
            }


            // Update existing pin.
            item.pin.background = markerColor;

            item.pin.glyphText = isCheapest
                ? "$"
                : "";

            item.pin.scale = isCheapest
                ? 1.2
                : 1.0;

            item.marker.zIndex = isCheapest
                ? 1000
                : 100;

        }


        // ----------------------------------------------
        // CLOSE POPUP IF ITS STATION IS HIDDEN
        // ----------------------------------------------

        if (state.activeStationId !== null) {

            const activeVisible = visibleStations.some(
                item =>
                    item.station.id ===
                    state.activeStationId
            );

            if (!activeVisible && state.infoWindow) {

                state.infoWindow.close();

                state.activeStationId = null;

            }

        }


        // ----------------------------------------------
        // UPDATE MAP SUMMARY
        // ----------------------------------------------

        if (!state.latestData.hasData) {

            countLabel.textContent = "—";

            bestLabel.textContent = "—";

            return;

        }

        countLabel.textContent =
            visibleStations.length.toString();


        if (bestStation) {

            bestLabel.textContent =
                bestStation.name +
                " — $" +
                bestStation.price.toFixed(2) +
                "/gal";

        } else {

            bestLabel.textContent =
                "No eligible prices within radius";

        }

    }


    // ==================================================
    // 6. CREATE SAFE STATION POPUP CONTENT
    // ==================================================

    function createStationPopup(station) {

        const container = document.createElement("div");

        container.style.fontFamily =
            "Arial, sans-serif";

        container.style.minWidth = "180px";


        // ----------------------------------------------
        // STATION NAME
        // ----------------------------------------------

        const heading = document.createElement("strong");

        heading.textContent = station.name;

        container.appendChild(heading);


        // ----------------------------------------------
        // REGULAR GAS PRICE
        // ----------------------------------------------

        const priceLine = document.createElement("p");

        let priceText = "Price unavailable";

        if (Number.isFinite(station.price)) {

            priceText =
                "$" +
                station.price.toFixed(2) +
                " per gallon";

            if (!station.eligible) {

                priceText +=
                    " (outside freshness limit)";

            }

        }

        priceLine.textContent = priceText;

        container.appendChild(priceLine);


        // ----------------------------------------------
        // DISTANCE
        // ----------------------------------------------

        const distanceLine =
            document.createElement("p");

        distanceLine.textContent =
            station.distance.toFixed(2) +
            " miles from campus";

        container.appendChild(distanceLine);


        // ----------------------------------------------
        // PRICE AGE
        // ----------------------------------------------

        if (Number.isFinite(station.age)) {

            const ageLine =
                document.createElement("small");

            ageLine.textContent =
                "Price age: " +
                station.age.toFixed(1) +
                " hours";

            container.appendChild(ageLine);

        }


        return container;

    }


    // ==================================================
    // 7. SYNCHRONIZE GAS STATION MARKERS
    // ==================================================

    function syncStationMarkers() {

        if (!state.map) {
            return;
        }

        const stations =
            state.latestData.stations || [];

        // Identify whether the actual station data changed.
        const signature = JSON.stringify(stations);


        if (signature !== state.stationSignature) {

            // ------------------------------------------
            // REMOVE PREVIOUS STATION MARKERS
            // ------------------------------------------

            for (const item of state.markers) {

                item.marker.map = null;

            }

            state.markers = [];

            if (state.infoWindow) {
                state.infoWindow.close();
            }

            state.activeStationId = null;


            // ------------------------------------------
            // CREATE NEW STATION MARKERS
            // ------------------------------------------

            for (const station of stations) {

                // Create colored station pin.
                const pin = new state.PinElement({

                    background: station.eligible
                        ? COLORS.eligible
                        : COLORS.unavailable,

                    borderColor: "#ffffff",

                    glyphColor: "#ffffff",

                    scale: 1

                });


                // Create marker.
                const marker =
                    new state.AdvancedMarkerElement({

                        map: state.map,

                        position: {
                            lat: station.lat,
                            lng: station.lng
                        },

                        title: station.name,

                        content: pin,

                        gmpClickable: true,

                        zIndex: 100

                    });


                // --------------------------------------
                // HANDLE MARKER CLICKS
                // --------------------------------------

                marker.addEventListener(
                    "gmp-click",
                    () => {

                        if (state.infoWindow) {

                            state.infoWindow.close();

                        }

                        const popup =
                            createStationPopup(station);

                        state.infoWindow.setContent(
                            popup
                        );

                        state.infoWindow.open({

                            map: state.map,

                            anchor: marker

                        });

                        state.activeStationId =
                            station.id;

                    }
                );


                state.markers.push({

                    station: station,

                    marker: marker,

                    pin: pin

                });

            }


            // Remember which dataset is displayed.
            state.stationSignature = signature;

        }


        // Apply current radius after data changes.
        updateMapRadius(
            Number(slider.value)
        );

    }


    // ==================================================
    // 8. SLIDER INTERACTIONS
    // ==================================================

    // Set the slider to the radius supplied by Python.
    const initialRadius = clampRadius(
        data.radius ?? 2.00
    );

    slider.value = initialRadius.toFixed(2);

    updateSliderAppearance(initialRadius);


    // ----------------------------------------------
    // LIVE UPDATES WHILE DRAGGING
    // ----------------------------------------------

    slider.oninput = () => {

        const newRadius = clampRadius(
            slider.value
        );

        updateMapRadius(newRadius);

    };


    // ----------------------------------------------
    // SYNCHRONIZE WITH STREAMLIT ON RELEASE
    // ----------------------------------------------

    slider.onchange = () => {

        const selectedRadius = clampRadius(
            slider.value
        );

        // Update Python state only when the user
        // commits the selected radius.
        setStateValue(
            "radius",
            selectedRadius
        );

    };


    // ==================================================
    // 9. LOAD GOOGLE MAPS JAVASCRIPT API
    // ==================================================

    async function loadGoogleMaps(apiKey) {

        // Google Maps may already be available.
        if (window.google?.maps?.importLibrary) {
            return;
        }


        // Share the loading promise across reruns.
        if (!window._gsuGoogleMapsPromise) {

            window._gsuGoogleMapsPromise = new Promise(
                (resolve, reject) => {

                    const callbackName =
                        "__gsuGoogleMapsReady";

                    window[callbackName] = () => {

                        delete window[callbackName];

                        resolve();

                    };


                    const script =
                        document.createElement("script");

                    script.src =
                        "https://maps.googleapis.com/maps/api/js" +
                        "?key=" +
                        encodeURIComponent(apiKey) +
                        "&loading=async" +
                        "&callback=" +
                        callbackName +
                        "&v=weekly";

                    script.async = true;


                    script.onerror = () => {

                        delete window[callbackName];

                        reject(
                            new Error(
                                "Google Maps JavaScript API " +
                                "failed to load."
                            )
                        );

                    };


                    document.head.appendChild(script);

                }
            ).catch(error => {

                window._gsuGoogleMapsPromise = null;

                throw error;

            });

        }


        await window._gsuGoogleMapsPromise;

    }


    // ==================================================
    // 10. INITIALIZE GOOGLE MAP
    // ==================================================

    async function initializeMap() {

        const currentData = state.latestData;

        // Use browser-restricted API key.
        await loadGoogleMaps(
            currentData.apiKey
        );


        // Load required Google Maps libraries.
        const { Map, Circle, InfoWindow } =
            await google.maps.importLibrary("maps");

        const {
            AdvancedMarkerElement,
            PinElement
        } = await google.maps.importLibrary("marker");


        state.AdvancedMarkerElement =
            AdvancedMarkerElement;

        state.PinElement =
            PinElement;


        // ----------------------------------------------
        // CREATE MAP ONCE
        // ----------------------------------------------

        if (!state.map) {

            const campus =
                state.latestData.campus;


            state.map = new Map(

                mapContainer,

                {
                    center: campus,

                    zoom: 12,

                    mapId: "DEMO_MAP_ID",

                    mapTypeControl: false,

                    fullscreenControl: true
                }

            );


            // ------------------------------------------
            // CREATE RADIUS CIRCLE ONCE
            // ------------------------------------------

            state.circle = new Circle({

                map: state.map,

                center: campus,

                radius:
                    Number(slider.value) *
                    MILES_TO_METERS,

                strokeColor: COLORS.radius,

                strokeOpacity: 0.8,

                strokeWeight: 2,

                fillColor: COLORS.radius,

                fillOpacity: 0.08

            });


            // ------------------------------------------
            // CREATE SHARED INFO WINDOW
            // ------------------------------------------

            state.infoWindow =
                new InfoWindow();


            // ------------------------------------------
            // CREATE GSU CAMPUS MARKER
            // ------------------------------------------

            const campusPin = new PinElement({

                background: COLORS.campus,

                borderColor: "#92400e",

                glyphColor: "#ffffff",

                glyphText: "G",

                scale: 1.3

            });


            new AdvancedMarkerElement({

                map: state.map,

                position: campus,

                content: campusPin,

                title: "GSU Buckhead Campus",

                zIndex: 2000

            });


            // ------------------------------------------
            // SET INITIAL MAP VIEW
            // ------------------------------------------

            // Fit the maximum search area once.
            // After this, moving the slider will not
            // repeatedly reset the map's zoom level.

            const maximumCircle = new Circle({

                center: campus,

                radius:
                    MAX_RADIUS * MILES_TO_METERS

            });

            const bounds =
                maximumCircle.getBounds();

            if (bounds) {

                state.map.fitBounds(bounds);

            }

        }


        // Add stations and apply the selected radius.
        syncStationMarkers();

    }


    // ==================================================
    // 11. UPDATE EXISTING MAP OR INITIALIZE NEW ONE
    // ==================================================

    if (state.map) {

        // Streamlit has rerun, but the existing map
        // can be reused.

        syncStationMarkers();

    } else if (!state.initializing) {

        // Initialize only once per mounted component.
        state.initializing = initializeMap()
            .catch(error => {

                console.error(
                    "GSU Google Maps error:",
                    error
                );

                state.initializing = null;

                mapContainer.textContent =
                    "Unable to load Google Maps. " +
                    "Check the browser console " +
                    "and API configuration.";

            });

    }

}
