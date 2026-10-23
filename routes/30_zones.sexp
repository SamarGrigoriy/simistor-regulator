	(zone
		(net "GND")
		(layer "B.Cu")
		(uuid "65e96e76-c821-4f78-a3b3-b804ab668730")
		(name "GND_B")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0.3)
		)
		(min_thickness 0.25)
		(fill yes
			(thermal_gap 0.4)
			(thermal_bridge_width 0.5)
			(island_removal_mode 0)
		)
		(polygon
			(pts
				(xy 142 100.3) (xy 179.7 100.3) (xy 179.7 169.7) (xy 142 169.7)
			)
		)
	)
	(zone
		(net "GND")
		(layer "F.Cu")
		(uuid "25289346-efcb-4cc0-99fc-d73ae34e04ae")
		(name "GND_F")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0.3)
		)
		(min_thickness 0.25)
		(fill yes
			(thermal_gap 0.4)
			(thermal_bridge_width 0.5)
			(island_removal_mode 0)
		)
		(polygon
			(pts
				(xy 142.6 100.3) (xy 179.7 100.3) (xy 179.7 169.7) (xy 142.6 169.7)
			)
		)
	)
	(zone
		(layer "F.Cu")
		(uuid "e49980fc-34f3-4106-bdd9-aabd61cac08b")
		(name "Головка винта H2")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0)
		)
		(min_thickness 0.25)
		(keepout
			(tracks not_allowed)
			(vias not_allowed)
			(pads allowed)
			(copperpour not_allowed)
			(footprints allowed)
		)
		(fill
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
		)
		(polygon
			(pts
				(xy 175.93 111.5) (xy 178.67 111.5) (xy 180.6 113.43) (xy 180.6 116.17)
				(xy 178.67 118.1) (xy 175.93 118.1) (xy 174 116.17) (xy 174 113.43)
			)
		)
	)
	(zone
		(layer "F.Cu")
		(uuid "f6c7cf61-3eff-4570-a8ed-fb206afa199d")
		(name "Головка винта H3")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0)
		)
		(min_thickness 0.25)
		(keepout
			(tracks not_allowed)
			(vias not_allowed)
			(pads allowed)
			(copperpour not_allowed)
			(footprints allowed)
		)
		(fill
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
		)
		(polygon
			(pts
				(xy 141.63 162.7) (xy 144.37 162.7) (xy 146.3 164.63) (xy 146.3 167.37)
				(xy 144.37 169.3) (xy 141.63 169.3) (xy 139.7 167.37) (xy 139.7 164.63)
			)
		)
	)
	(zone
		(layers "F.Cu" "B.Cu")
		(uuid "fb72a18a-a431-45a0-9e74-bf8b24c7b850")
		(name "Q101_PINS")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0)
		)
		(min_thickness 0.25)
		(keepout
			(tracks allowed)
			(vias allowed)
			(pads allowed)
			(copperpour allowed)
			(footprints allowed)
		)
		(fill
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
		)
		(polygon
			(pts
				(xy 121.5 150.4) (xy 126 150.4) (xy 126 158.5) (xy 121.5 158.5)
			)
		)
	)
