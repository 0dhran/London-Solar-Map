# London-Solar-Map
Tool to identify potential Community Solar sites in Southwark and possibly more broadly 

**Q** We have the Community Energy London Potential Map - why is this not being used? Is it being used? I suppose an in house map helps us to track things better as we can set it up how we like it more (?)

# Motivation
At Community Energy Southwark a large part of work (let's get an estimate) is the identifying of potential solar sites - this can be done through recommendation or through a dedicated map site search.

When carrying out the map site search, there are many steps:
- Check the London Solar Opportunity Map (LSOM) to identify buildings where the solar potential is significantly high.
- Inspect potential sites on Google Earth (satellite imagery) to see if the roof is sufficiently clear of clutter to have solar PVs installed.
- Check the Land Registry to see who owns the potential site / is it a registered building.

Admittedly, its not horrendously inefficient, however it struck me that there must be a huge amount of duplication of work from people searching over the same area many times (could yet be proven wrong on this!). When the process was demo'ed to me, it also took some time to identify the building on Google Earth from LSOM. It seems reasonable that a tool that links different databases (satellite, solar opportunity, ownership info) would streamline the process, allowing for filtering by different metrics (e.g. only schools etc), as well as co-ordinating where has previously been searched. Ideally, the tool would also be open source and useable across different cities or contexts. Depending on the strength of the use case, could also make an updateable framework using satellite imagery / LiDAR and machine learning where a model checks for changes in building roofs. 

**Q** Can we get Smart Meter data to identify places with high daily electricity use that may map up well with solar profiles.

Initial Conception of the Framework : 
- Link the LSOM, registry info, and satellite imagery.
- Some record of places previously searched and for filtering for unsearched places.

Framing as an academic paper : 
Not sure the best way to do this, like it can be purely technical, or could be more about the impact of the tool on process in CES (in a public health way?). Maybe try frame it as 'can the use of machine learning have a positive public health effect?' 

I reckon a case-study, just documenting how effective it's been - probably mentioning changes in effectiveness, and maybe going into other things. Perplexity recommended formally testing if the search quality decreased which seems overkill right now since we're not operating at full capacity. 


**Steps**
1. Link registry and satellite/Google Earth
2. Link to LSOM
3. Create a platform that can filter and store info

Potential expansions:
- Abandon LSOM for OpenStreetMap or similar (buildings) to avoid Ordnance Survey copyright issues with making open source. Requires creating our own model of solar opportunity.

# Data

**LSOM** This data is geolinked via OS TOIDs. To use these we must refer back to the OS MasterMap. This is available under license and expensive (££££'s). However, can get an End User License from Southwark Council as they are a Public Service Geospatial Agreement (PSGA) member. Need to contact Southwark and see if they're happy to do this. Should in theory then be easy to link data from here.

**Satellite** Currently use Google Earth.

**Land Registry** 

