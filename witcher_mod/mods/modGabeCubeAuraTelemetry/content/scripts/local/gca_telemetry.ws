// GabeCubeAura telemetry bridge for The Witcher 3 Complete Edition 5.00+.
// The bounded state file is the primary transport. Namespaced script-log
// records remain available as an independent diagnostic fallback.

@addField(W3PlayerWitcher) private var gcaTelemetryElapsed : float;
@addField(W3PlayerWitcher) private var gcaTelemetryFileElapsed : float;

@addMethod(W3PlayerWitcher)
private function GCAWriteTelemetryState(record : string)
{
    var config : CInGameConfigWrapper;
    var stamp : string;

    config = (CInGameConfigWrapper)theGame.GetInGameConfigWrapper();
    if ( config )
    {
        stamp = IntToString(theGame.GetLocalTimeAsMilliseconds());
        config.WriteIniFile("GabeCubeAuraTelemetry.ini", "state", record);
        config.WriteIniFile("GabeCubeAuraTelemetry.ini", "state_stamp", stamp);
    }
}

@addMethod(W3PlayerWitcher)
private function GCAWriteTelemetrySign(record : string)
{
    var config : CInGameConfigWrapper;
    var stamp : string;

    config = (CInGameConfigWrapper)theGame.GetInGameConfigWrapper();
    if ( config )
    {
        stamp = IntToString(theGame.GetLocalTimeAsMilliseconds());
        config.WriteIniFile("GabeCubeAuraTelemetry.ini", "sign", record);
        config.WriteIniFile("GabeCubeAuraTelemetry.ini", "sign_stamp", stamp);
    }
}

@addMethod(W3PlayerWitcher)
private function GCAEmitTelemetryState(writeStateFile : bool)
{
    var combat : string;
    var record : string;

    if ( IsInCombat() )
        combat = "1";
    else
        combat = "0";

    record =
        "GCA1|kind=state" +
        "|health=" + NoTrailZeros(GetStat(BCS_Vitality)) +
        "|health_max=" + NoTrailZeros(GetStatMax(BCS_Vitality)) +
        "|stamina=" + NoTrailZeros(GetStat(BCS_Stamina)) +
        "|stamina_max=" + NoTrailZeros(GetStatMax(BCS_Stamina)) +
        "|toxicity=" + NoTrailZeros(GetStat(BCS_Toxicity)) +
        "|toxicity_max=" + NoTrailZeros(GetStatMax(BCS_Toxicity)) +
        "|adrenaline=" + NoTrailZeros(GetStat(BCS_Focus)) +
        "|combat=" + combat;

    LogChannel('GabeCubeAura', record);
    if ( writeStateFile )
    {
        GCAWriteTelemetryState(record);
    }
}

@wrapMethod(W3PlayerWitcher)
function OnPlayerTickTimer(deltaTime : float)
{
    var writeStateFile : bool;

    wrappedMethod(deltaTime);

    gcaTelemetryElapsed += deltaTime;
    gcaTelemetryFileElapsed += deltaTime;
    if ( gcaTelemetryFileElapsed >= 0.25f )
    {
        gcaTelemetryFileElapsed = 0.f;
        writeStateFile = true;
    }

    if ( gcaTelemetryElapsed >= 0.10f )
    {
        gcaTelemetryElapsed = 0.f;
        GCAEmitTelemetryState(writeStateFile);
    }
}

@wrapMethod(W3PlayerWitcher)
function OnSignCastPerformed(signType : ESignType, isAlternate : bool)
{
    var record : string;

    wrappedMethod(signType, isAlternate);
    record = "GCA1|kind=sign|sign=" + SignEnumToString(signType);
    LogChannel('GabeCubeAura', record);
    GCAWriteTelemetrySign(record);
}
