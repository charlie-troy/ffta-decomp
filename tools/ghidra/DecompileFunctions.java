// Decompile the functions whose addresses are given as script arguments and
// write the C to a file.
//
//   analyzeHeadless <proj> <name> -process baserom.gba \
//       -scriptPath tools/ghidra -postScript DecompileFunctions.java <out> <addr>...
//
// Ghidra's C is never byte-matching. It is a structurally correct starting
// point to refine through the compile-and-diff pipeline, which is what makes
// functions too large to read by eye approachable.
//@category FFTA

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.Function;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.math.BigInteger;

public class DecompileFunctions extends GhidraScript {

    /** Bytes re-decoded as Thumb around each requested address. */
    private static final int WINDOW = 0x100;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: DecompileFunctions <outfile> <addr>...");
            return;
        }

        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);

        PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        int ok = 0, failed = 0;

        for (int i = 1; i < args.length; i++) {
            String addrText = args[i];
            Address addr = toAddr(addrText);

            // The GBA runs almost entirely in Thumb, but a raw binary import
            // has no way to know that, so auto-analysis decodes ARM and the
            // decompiler emits halt_baddata(). TMode=1 fixes it, but the
            // context register cannot be changed where instructions already
            // exist, so the listing must be cleared FIRST.
            Address end = addr.add(WINDOW - 1);
            clearListing(addr, end);

            Register tmode = currentProgram.getRegister("TMode");
            if (tmode != null) {
                currentProgram.getProgramContext().setRegisterValue(
                        addr, end, new RegisterValue(tmode, BigInteger.ONE));
            }
            disassemble(addr);

            Function f = getFunctionAt(addr);
            if (f == null) {
                f = createFunction(addr, null);
            }
            out.println("/* ===== " + addrText + " ===== */");
            if (f == null) {
                out.println("/* no function could be created here */");
                failed++;
                continue;
            }
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            if (res != null && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
                ok++;
            } else {
                String msg = (res == null) ? "null result" : res.getErrorMessage();
                out.println("/* decompile failed: " + msg + " */");
                failed++;
            }
            out.println();
        }

        out.close();
        di.dispose();
        println("decompiled " + ok + ", failed " + failed + " -> " + args[0]);
    }
}
