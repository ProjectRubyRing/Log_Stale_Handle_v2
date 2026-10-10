import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.Random;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * 6 タスク検証用のアプリ（JBoss の上で動く業務アプリの代わり）。
 *
 *   トレースログ : Logger "jp.iwin.base.tango.ILGLog4j.trace" に debug で 1 件ずつ書く（ユーザーの設定と同じ名前）。
 *                  メッセージに「時刻 task=<名前> seq=<連番>」を入れる（既定のレイアウト %m%n なので、時刻は自分で入れる）。
 *   server.log   : Logger "server" に 10 件に 1 件（JBoss の server.log の代わり。タスクごとのディレクトリ）。
 *   正解の台帳   : /tmp/ledger.tsv（コンテナのローカルディスク）に「連番 TAB エポックミリ秒」。
 *                  あとで EFS（NFS）上に残った行と突き合わせて、どの行がどこへ行ったか・消えたかを数える。
 *
 * 環境変数: TASK_NAME, DURATION_SEC（動かす秒数）, MIN_MS / MAX_MS（書く間隔の範囲・リクエストの到着のばらつき）, SEED
 */
public class TraceLab {
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("HH:mm:ss.SSS");

    static String env(String k, String d) {
        String v = System.getenv(k);
        return (v == null || v.isEmpty()) ? d : v;
    }

    public static void main(String[] args) throws Exception {
        String task = env("TASK_NAME", "T0");
        long duration = Long.parseLong(env("DURATION_SEC", "250"));
        int min = Integer.parseInt(env("MIN_MS", "100"));
        int max = Integer.parseInt(env("MAX_MS", "400"));
        Random rnd = new Random(Long.parseLong(env("SEED", "1")));

        Logger trace = LogManager.getLogger("jp.iwin.base.tango.ILGLog4j.trace");
        Logger server = LogManager.getLogger("server");

        long end = System.currentTimeMillis() + duration * 1000L;
        long seq = 0;
        System.out.println(LocalTime.now().format(TS) + " START task=" + task);
        try (PrintWriter ledger = new PrintWriter(Files.newBufferedWriter(Paths.get("/tmp/ledger.tsv")))) {
            while (System.currentTimeMillis() < end) {
                seq++;
                long now = System.currentTimeMillis();
                trace.debug("{} task={} seq={}", LocalTime.now().format(TS), task, seq);
                ledger.println(seq + "\t" + now);
                if (seq % 10 == 0) {
                    server.info("{} task={} server seq={}", LocalTime.now().format(TS), task, seq);
                }
                Thread.sleep(min + rnd.nextInt(max - min + 1));
            }
        }
        System.out.println(LocalTime.now().format(TS) + " SUMMARY task=" + task + " events=" + seq);
        LogManager.shutdown();
    }
}
